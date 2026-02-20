from collections.abc import Iterator
from enum import StrEnum
from typing import Any


class TraceLibraryPayloadFormat(StrEnum):
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


class DataDogTrace:
    """Wrapper around trace object reported by dd-trace libraries"""

    def __init__(self, data: dict, raw_trace: dict | list[dict]):
        self.data = data
        """raw requests and responses sent to the agent"""

        self.raw_trace = raw_trace
        """raw trace object"""

        self.format: TraceLibraryPayloadFormat = {
            "/v0.4/traces": TraceLibraryPayloadFormat.v04,
            "/v0.5/traces": TraceLibraryPayloadFormat.v05,
            "/v1.0/traces": TraceLibraryPayloadFormat.v10,
        }[data["path"]]

        if self.format == TraceLibraryPayloadFormat.v10:
            spans = self.raw_trace_v_1_0["spans"]
        elif self.format == TraceLibraryPayloadFormat.v05:
            spans = self.raw_trace_v_0_4
        else:
            spans = self.raw_trace_v_0_4

        self.spans = [DataDogSpan(self, s) for s in spans]

    @property
    def raw_trace_v_1_0(self) -> dict:
        assert isinstance(self.raw_trace, dict)
        return self.raw_trace

    @property
    def raw_trace_v_0_4(self) -> list[dict]:
        assert isinstance(self.raw_trace, list)
        return self.raw_trace

    @property
    def trace_id(self) -> str:
        if self.format == TraceLibraryPayloadFormat.v10:
            return self.raw_trace_v_1_0["trace_id"]

        return self.raw_trace_v_0_4[0]["trace_id"]

    @property
    def log_filename(self) -> str:
        return self.data["log_filename"]

    def __iter__(self) -> Iterator["DataDogSpan"]:
        """Iterate over spans"""
        yield from self.spans

    def __getitem__(self, i: int) -> "DataDogSpan":
        """Get the ith spans"""
        return self.spans[i]

    def __len__(self) -> int:
        """Return span count"""
        return len(self.spans)


class DataDogSpan:
    """Wrapper around trace object reported by dd-trace libraries"""

    def __init__(self, trace: DataDogTrace, raw_data: dict):
        self.trace = trace

        self.raw_data = raw_data

    def get(self, key: str, default: Any = None):  # noqa: ANN401
        if key == "trace_id":
            return self.trace.trace_id

        if key in ("meta", "meta_struct", "metrics") and self.trace.format == TraceLibraryPayloadFormat.v10:
            return self.raw_data["attributes"]

        return self.raw_data.get(key, default)

    def __getitem__(self, key: str):
        if key == "trace_id":
            return self.trace.trace_id

        if key in ("meta", "meta_struct", "metrics") and self.trace.format == TraceLibraryPayloadFormat.v10:
            return self.raw_data["attributes"]

        return self.raw_data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.raw_data
