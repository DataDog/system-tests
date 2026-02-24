from abc import ABC, abstractmethod
from collections.abc import Iterator
from enum import StrEnum
from typing import Any


class LibraryTraceFormat(StrEnum):
    """Describe which format is used to carry trace payloads from the library to the agent
    This enum is used only in system-tests to differentiate between different library payloads
    and is not exposed directly in trace payloads.
    """

    v04 = "v0.4"
    """ v0.4 format - list of spans with meta/metrics separated"""

    v05 = "v0.5"
    """ v0.5 format - list of spans with meta/metrics separated"""

    v10 = "v1.0"
    """ v1.0 format - chunks with spans using attributes and name_value/type_value fields
    RFC: https://docs.google.com/document/d/1hNS6anKYutOYW-nmR759UlKXUdT6H0mRwVt7_L70ESc/edit?usp=sharing"""


class DataDogLibraryTrace(ABC):
    """Wrapper around trace object reported by dd-trace libraries"""

    data: dict
    """raw request and response sent to the agent"""

    format: LibraryTraceFormat

    raw_trace: dict | list[dict]
    """raw trace object"""

    spans: list["DataDogLibrarySpan"]

    @staticmethod
    def from_legacy(data: dict, raw_trace: list[dict]) -> "DataDogLibraryTrace":
        return DataDogLibraryTraceLegacy(data, raw_trace)

    @staticmethod
    def from_v1(data: dict, raw_trace: dict) -> "DataDogLibraryTracev1":
        return DataDogLibraryTracev1(data, raw_trace)

    @property
    @abstractmethod
    def trace_id(self) -> str | int:
        pass

    @property
    @abstractmethod
    def trace_id_as_int(self) -> int:
        pass

    @property
    def log_filename(self) -> str:
        return self.data["log_filename"]

    def trace_id_equals(self, other: int | str) -> bool:
        if isinstance(other, str):
            assert other.startswith("0x")
            other = int(other, 16) & 0xFFFFFFFFFFFFFFFF

        return other == self.trace_id_as_int

    def __iter__(self) -> Iterator["DataDogLibrarySpan"]:
        """Iterate over spans"""
        yield from self.spans

    def __getitem__(self, i: int) -> "DataDogLibrarySpan":
        """Get the ith spans"""
        return self.spans[i]

    def __len__(self) -> int:
        """Return span count"""
        return len(self.spans)


class DataDogLibraryTraceLegacy(DataDogLibraryTrace):
    def __init__(self, data: dict, raw_trace: list[dict]):
        self.data = data

        self.raw_trace: list[dict] = raw_trace

        self.format: LibraryTraceFormat = {
            "/v0.4/traces": LibraryTraceFormat.v04,
            "/v0.5/traces": LibraryTraceFormat.v05,
        }[data["path"]]

        self.spans = [DataDogLibrarySpanLegacy(self, s) for s in self.raw_trace]

    @property
    def trace_id(self) -> int:
        return self.raw_trace[0]["trace_id"]

    @property
    def trace_id_as_int(self) -> int:
        return self.trace_id


class DataDogLibraryTracev1(DataDogLibraryTrace):
    def __init__(self, data: dict, raw_trace: dict):
        self.data = data

        self.raw_trace: dict = raw_trace

        self.format = LibraryTraceFormat.v10

        self.spans = [DataDogLibrarySpanV1(self, s) for s in self.raw_trace["spans"]]

    @property
    def trace_id(self) -> str | int:
        return self.raw_trace["trace_id"]

    @property
    def trace_id_as_int(self) -> int:
        return int(self.raw_trace["trace_id"], 16) & 0xFFFFFFFFFFFFFFFF


class DataDogLibrarySpan(ABC):
    """Wrapper around trace object reported by dd-trace libraries"""

    def __init__(self, trace: DataDogLibraryTrace, raw_span: dict):
        self.trace = trace

        self.raw_span = raw_span

    def __contains__(self, key: str) -> bool:
        return key in self.raw_span

    @abstractmethod
    def get(self, key: str, default: Any = None):  # noqa: ANN401
        pass

    @abstractmethod
    def __getitem__(self, key: str):
        pass


class DataDogLibrarySpanLegacy(DataDogLibrarySpan):
    def get(self, key: str, default: Any = None):  # noqa: ANN401
        return self.raw_span.get(key, default)

    def __getitem__(self, key: str):
        return self.raw_span[key]


class DataDogLibrarySpanV1(DataDogLibrarySpan):
    def __contains__(self, key: str) -> bool:
        if key in ("meta", "meta_struct", "metrics"):
            return "attributes" in self.raw_span

        if key == "trace_id":
            return True

        return key in self.raw_span

    def get(self, key: str, default: Any = None):  # noqa: ANN401
        if key == "trace_id":
            return self.trace.trace_id

        if key in ("meta", "meta_struct", "metrics"):
            return self.raw_span["attributes"]

        return self.raw_span.get(key, default)

    def __getitem__(self, key: str):
        if key == "trace_id":
            return self.trace.trace_id

        if key in ("meta", "meta_struct", "metrics"):
            return self.raw_span["attributes"]

        return self.raw_span[key]
