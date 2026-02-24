from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class AgentTraceFormat(StrEnum):
    """Describe which format is used to carry trace payloads from the agent to the backend"""

    legacy = "legacy"
    """ Legacy format before agent version 7.73.0"""

    efficient_trace_payload_format = "efficient_trace_payload_format"
    """ Efficient format introduced in agent version 7.73.0. Uses idxTracerPayloads field instead of tracerPayloads
    RFC: https://docs.google.com/document/d/1hNS6anKYutOYW-nmR759UlKXUdT6H0mRwVt7_L70ESc/edit?usp=sharing"""


class DataDogAgentTrace(ABC):
    """Wrapper around trace object reported by dd-trace libraries"""

    data: dict
    """raw request and response sent to the agent"""

    format: AgentTraceFormat

    raw_trace: dict | list[dict]
    """raw trace object"""

    spans: list["DataDogAgentSpan"]

    @staticmethod
    def from_agent_legacy(data: dict, raw_trace: dict) -> "DataDogTraceAgentLegacy":
        return DataDogTraceAgentLegacy(data, raw_trace)

    @staticmethod
    def from_agent_v1(data: dict, raw_trace: dict) -> "DataDogTraceAgentV1":
        return DataDogTraceAgentV1(data, raw_trace)

    @property
    @abstractmethod
    def trace_id(self) -> int | str:
        """Returns the trace ID of a trace according to its format
        it may be a int with legacy format, of a string on efficient format
        """

    @property
    @abstractmethod
    def trace_id_as_int(self) -> int:
        """Returns the trace ID of a trace
        Returns only the lower 64 bits of the trace ID
        """

    @property
    def log_filename(self) -> str:
        return self.data["log_filename"]

    def __len__(self) -> int:
        """Return span count"""
        return len(self.spans)


class DataDogTraceAgentLegacy(DataDogAgentTrace):
    # spans: list["DataDogAgentSpanLegacy"]

    def __init__(self, data: dict, raw_trace: dict):
        self.data = data

        self.raw_trace: dict = raw_trace

        self.format = AgentTraceFormat.legacy

        self.spans = [DataDogAgentSpanLegacy(self, s) for s in self.raw_trace["spans"]]

    @property
    def trace_id(self) -> int:
        return self.spans[0]["traceID"]

    @property
    def trace_id_as_int(self) -> int:
        return self.spans[0]["traceID"]


class DataDogTraceAgentV1(DataDogAgentTrace):
    # spans: list["DataDogAgentSpanV10"]

    def __init__(self, data: dict, raw_trace: dict):
        self.data = data

        self.raw_trace: dict = raw_trace

        self.format = AgentTraceFormat.efficient_trace_payload_format

        self.spans = [DataDogAgentSpanV10(self, s) for s in self.raw_trace["spans"]]

    @property
    def trace_id(self) -> str:
        return self.raw_trace["traceID"]

    @property
    def trace_id_as_int(self) -> int:
        return int(self.trace_id, 16) & 0xFFFFFFFFFFFFFFFF


class DataDogAgentSpan(ABC):
    """Wrapper around trace object reported by dd-trace libraries"""

    def __init__(self, trace: DataDogAgentTrace, raw_span: dict):
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

    @property
    @abstractmethod
    def meta(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_span_type(self) -> str:
        pass

    @abstractmethod
    def get_span_name(self) -> str:
        pass

    @abstractmethod
    def get_span_resource(self) -> str:
        pass

    @abstractmethod
    def get_span_service(self) -> str:
        pass

    @abstractmethod
    def get_span_kind(self) -> str:
        pass


class DataDogAgentSpanLegacy(DataDogAgentSpan):
    def get(self, key: str, default: Any = None):  # noqa: ANN401
        return self.raw_span.get(key, default)

    def __getitem__(self, key: str):
        return self.raw_span[key]

    @property
    def meta(self) -> dict[str, Any]:
        return self.raw_span["meta"]

    def get_span_type(self) -> str:
        return self.raw_span.get("type", "")

    def get_span_name(self) -> str:
        return self.raw_span["name"]

    def get_span_resource(self) -> str:
        return self.raw_span["resource"]

    def get_span_service(self) -> str:
        return self.raw_span["service"]

    def get_span_kind(self) -> str:
        return self.meta["span.kind"]


class DataDogAgentSpanV10(DataDogAgentSpan):
    def get(self, key: str, default: Any = None):  # noqa: ANN401
        return self.raw_span.get(key, default)

    def __getitem__(self, key: str):
        return self.raw_span[key]

    @property
    def meta(self) -> dict[str, Any]:
        return self.raw_span["attributes"]

    def get_span_type(self) -> str:
        return self.raw_span.get("typeRef", "")

    def get_span_name(self) -> str:
        return self.raw_span["nameRef"]

    def get_span_resource(self) -> str:
        return self.raw_span["resourceRef"]

    def get_span_service(self) -> str:
        return self.raw_span["serviceRef"]

    def get_span_kind(self) -> str:
        return self.raw_span["kind"]
