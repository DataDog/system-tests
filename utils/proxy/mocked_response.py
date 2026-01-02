from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from collections import defaultdict
from http import HTTPStatus
import json
import os
import re
import requests

from mitmproxy.http import HTTPFlow, Response as HTTPResponse

from .ports import ProxyPorts

MOCKED_TRACER_RESPONSES_PATH = "/mocked_tracer_responses"
MOCKED_BACKEND_RESPONSES_PATH = "/mocked_backend_responses"


def _all_subclasses(cls: type[MockedResponse]) -> list[type[MockedResponse]]:
    result = []
    for subclass in cls.__subclasses__():
        result.append(subclass)
        result.extend(_all_subclasses(subclass))
    return result


def _get_proxy_domain() -> str:
    """Get the proxy domain from environment variables."""
    if "SYSTEM_TESTS_PROXY_HOST" in os.environ:
        return os.environ["SYSTEM_TESTS_PROXY_HOST"]
    if "DOCKER_HOST" in os.environ:
        m = re.match(r"(?:ssh:|tcp:|fd:|)//(?:[^@]+@|)([^:]+)", os.environ["DOCKER_HOST"])
        return m.group(1) if m is not None else "localhost"
    return "localhost"


class MockedResponse(ABC):
    """Abstract base class for all mocked responses (tracer and backend).

    This is the common interface for mocking HTTP responses in the proxy.
    """

    def __init__(self, path: str):
        self.path = path
        """Which path this mock applies to"""

    def __str__(self):
        return f"<{self.__class__.__name__} path={self.path}>"

    @abstractmethod
    def execute(self, flow: HTTPFlow) -> None:
        """Apply this mock to the HTTP flow."""

    def to_json(self) -> dict:
        """Serialize for transmission to proxy."""
        return {
            "type": self.__class__.__name__,
            "path": self.path,
        }

    @classmethod
    def from_json(cls, source: dict) -> MockedResponse:
        """Deserialize from JSON."""
        return cls(**source)

    @classmethod
    def build_from_json(cls, source: dict) -> MockedResponse:
        """Factory: create correct subclass from JSON."""
        mocked_response_type = source.pop("type")

        # Check if it matches the class itself (for non-abstract classes)
        if cls.__name__ == mocked_response_type:
            return cls.from_json(source)

        # Search subclasses
        for klass in _all_subclasses(cls):
            if klass.__name__ == mocked_response_type:
                return klass.from_json(source)

        raise ValueError(f"Unknown MockedResponse type: {mocked_response_type}")

    def _send_to_endpoint(self, endpoint_path: str) -> None:
        """Common HTTP PUT logic to send mock to proxy."""
        domain = _get_proxy_domain()
        response = requests.put(
            f"http://{domain}:{ProxyPorts.proxy_commands}{endpoint_path}",
            json=[self.to_json()],
            timeout=30,
        )
        response.raise_for_status()

    @abstractmethod
    def send(self) -> None:
        """Send instruction to the proxy to apply this mocked response."""


# =============================================================================
# Tracer Mocked Responses
# =============================================================================


class MockedTracerResponse(MockedResponse):
    """Base class for mocking responses from agent to tracer.

    These mocks modify existing responses after the request has been forwarded
    to the agent and a response received. The flow.response already exists
    when execute() is called.
    """

    def __init__(self, path: str, mocked_headers: dict | None = None):
        super().__init__(path)
        self.mocked_headers = mocked_headers
        """Overwrite existing headers with these ones. Set to None to keep existing headers"""

    @classmethod
    def build_from_json(cls, source: dict) -> MockedTracerResponse:
        """Factory: create correct MockedTracerResponse subclass from JSON."""
        result = super().build_from_json(source)
        assert isinstance(result, MockedTracerResponse)
        return result

    def execute(self, flow: HTTPFlow) -> None:
        """Modify the existing response from agent."""
        self._apply_status_code(flow)
        self._apply_headers(flow)

    def _apply_status_code(self, flow: HTTPFlow) -> None:
        flow.response.status_code = 200

    def _apply_headers(self, flow: HTTPFlow) -> None:
        if self.mocked_headers is None:
            return

        for key, value in self.mocked_headers.items():
            flow.response.headers[key] = value

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "path": self.path,
            "mocked_headers": self.mocked_headers,
        }

    def send(self) -> None:
        """Send instruction to the proxy at /mocked_tracer_responses endpoint."""
        self._send_to_endpoint(MOCKED_TRACER_RESPONSES_PATH)


class StaticJsonMockedTracerResponse(MockedTracerResponse):
    """Always overwrites the same static JSON content on request made on the given path."""

    def __init__(self, path: str, mocked_json: dict | list, status_code: int = 200):
        super().__init__(path=path, mocked_headers={"Content-Type": "application/json"})
        self.mocked_json = mocked_json
        """Content of the static JSON response"""
        self.status_code = status_code

    def _apply_status_code(self, flow: HTTPFlow) -> None:
        flow.response.status_code = self.status_code

    def execute(self, flow: HTTPFlow) -> None:
        super().execute(flow)
        flow.response.content = json.dumps(self.mocked_json).encode()

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "path": self.path,
            "mocked_json": self.mocked_json,
            "status_code": self.status_code,
        }


class SequentialRemoteConfigJsonMockedTracerResponse(MockedTracerResponse):
    """Overwrites JSON content on request made on /v0.7/config with a sequence of predefined responses."""

    def __init__(self, mocked_json_sequence: list[dict]):
        super().__init__(path="/v0.7/config", mocked_headers={"Content-Type": "application/json"})
        self.mocked_json_sequence = mocked_json_sequence
        """Sequence of JSON responses to return"""

        self._runtime_ids_request_count: dict[str, int] = defaultdict(int)
        """Tracks how many requests have been made per runtime ID"""

    def execute(self, flow: HTTPFlow) -> None:
        super().execute(flow)

        request_content = json.loads(flow.request.content)
        runtime_id = request_content["client"]["client_tracer"]["runtime_id"]
        nth_api_command = self._runtime_ids_request_count[runtime_id]
        response = self.mocked_json_sequence[nth_api_command]

        flow.response.content = json.dumps(response).encode()
        flow.response.headers["st-proxy-overwrite-rc-response"] = f"{nth_api_command}"

        if nth_api_command + 1 < len(self.mocked_json_sequence):
            self._runtime_ids_request_count[runtime_id] = nth_api_command + 1

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "mocked_json_sequence": self.mocked_json_sequence,
        }


class _InternalMockedTracerResponse(MockedTracerResponse):
    """Tracer mocked responses that will be applied on the entire test session.

    These cannot be sent via the API and must be configured at proxy startup.
    """

    def send(self) -> None:
        raise ValueError("This mocked response cannot be sent directly")

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
        }


class AddRemoteConfigEndpoint(_InternalMockedTracerResponse):
    """Adds /v0.7/config to the agent's /info endpoint list."""

    def __init__(self):
        super().__init__(path="/info")

    def execute(self, flow: HTTPFlow) -> None:
        if flow.response.status_code == HTTPStatus.OK:
            content = json.loads(flow.response.content)

            if "/v0.7/config" not in content["endpoints"]:
                content["endpoints"].append("/v0.7/config")
                flow.response.content = json.dumps(content).encode()


class RemoveMetaStructsSupport(_InternalMockedTracerResponse):
    """Removes span_meta_structs from agent's /info response."""

    def __init__(self):
        super().__init__(path="/info")

    def execute(self, flow: HTTPFlow) -> None:
        if flow.response.status_code == HTTPStatus.OK:
            c = json.loads(flow.response.content)
            if "span_meta_structs" in c:
                c.pop("span_meta_structs")
                flow.response.content = json.dumps(c).encode()


class SetSpanEventFlags(_InternalMockedTracerResponse):
    """Modify the agent flag that signals support for native span event serialization.

    There are three possible cases:
    - Not configured: agent's response is not modified, the real agent behavior is preserved
    - `true`: agent advertises support for native span events serialization
    - `false`: agent advertises that it does not support native span events serialization
    """

    def __init__(self, *, span_events: bool):
        super().__init__(path="/info")
        self.span_events = span_events
        """Value to set the span_events flag to"""

    def execute(self, flow: HTTPFlow) -> None:
        if flow.response.status_code == HTTPStatus.OK:
            c = json.loads(flow.response.content)
            c["span_events"] = self.span_events
            flow.response.content = json.dumps(c).encode()

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "span_events": self.span_events,
        }


# =============================================================================
# Backend Mocked Responses
# =============================================================================


class MockedBackendResponse(MockedResponse):
    """Base class for mocking responses from backend to agent.

    These mocks create new responses without forwarding the request to any
    upstream server. The flow.response does not exist when execute() is called.
    The content is pre-built by the caller (protobuf, JSON, plain text bytes).
    """

    def __init__(
        self,
        path: str,
        content: bytes,
        content_type: str = "application/x-protobuf",
        status_code: int = 200,
    ):
        super().__init__(path)
        self.content = content
        """Pre-built response bytes (protobuf, JSON, plain text)"""
        self.content_type = content_type
        """Content-Type header value"""
        self.status_code = status_code
        """HTTP status code"""

    @classmethod
    def build_from_json(cls, source: dict) -> MockedBackendResponse:
        """Factory: create correct MockedBackendResponse subclass from JSON."""
        result = super().build_from_json(source)
        assert isinstance(result, MockedBackendResponse)
        return result

    def execute(self, flow: HTTPFlow) -> None:
        """Create a new response (flow.response does not exist yet)."""

        flow.response = HTTPResponse.make(
            self.status_code,
            self.content,
            {"Content-Type": self.content_type},
        )

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "path": self.path,
            "content": base64.b64encode(self.content).decode("utf-8"),
            "content_type": self.content_type,
            "status_code": self.status_code,
        }

    @classmethod
    def from_json(cls, source: dict) -> MockedBackendResponse:
        """Deserialize from JSON, decoding base64 content."""
        source["content"] = base64.b64decode(source["content"])
        return cls(**source)

    def send(self) -> None:
        """Send instruction to the proxy at /mocked_backend_responses endpoint."""
        self._send_to_endpoint(MOCKED_BACKEND_RESPONSES_PATH)


class _InternalMockedBackendResponse(MockedBackendResponse):
    """Backend mocked responses that will be applied on the entire test session.

    These cannot be sent via the API and must be configured at proxy startup.
    """

    def send(self) -> None:
        raise ValueError("This mocked response cannot be sent directly")
