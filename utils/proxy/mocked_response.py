from collections import defaultdict
from http import HTTPStatus
import json
import os
import re
import requests

from mitmproxy.http import HTTPFlow

from .ports import ProxyPorts

MOCKED_RESPONSES_PATH = "/mocked_responses"


def _all_subclasses(cls: type["MockedResponse"]) -> list[type["MockedResponse"]]:
    result = []
    for subclass in cls.__subclasses__():
        result.append(subclass)
        result.extend(_all_subclasses(subclass))
    return result


class MockedResponse:
    """Instruction sent to the proxy to overwrite responses from agents"""

    def __init__(self, path: str, mocked_headers: dict | None = None):
        self.path = path
        """ Which agent path recieved the request """

        self.mocked_headers = mocked_headers
        """ Overwrite existing headers with these ones. Set to None to keep existing headers """

    def __str__(self):
        return f"<{self.__class__.__name__} path={self.path}>"

    def execute(self, flow: HTTPFlow) -> None:
        self._apply_status_code(flow)
        self._apply_headers(flow)

    def _apply_status_code(self, flow: HTTPFlow) -> None:
        flow.response.status_code = 200

    def _apply_headers(self, flow: HTTPFlow) -> None:
        if self.mocked_headers is None:
            return

        for key, value in self.mocked_headers.items():
            flow.response.headers[key] = value

    @classmethod
    def build_from_json(cls, source: dict) -> "MockedResponse":
        """Factory to create the right MockedResponse subclass from json data"""
        mocked_response_type = source.pop("type")

        for klass in _all_subclasses(cls):
            if klass.__name__ == mocked_response_type:
                return klass.from_json(source)

        raise ValueError(f"Unknown MockedResponse type: {mocked_response_type}")

    @classmethod
    def from_json(cls, source: dict) -> "MockedResponse":
        return cls(**source)

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "path": self.path,
            "mocked_headers": self.mocked_headers,
        }

    def send(self) -> None:
        """Send instruction to the proxy to apply this mocked response"""
        if "SYSTEM_TESTS_PROXY_HOST" in os.environ:
            domain = os.environ["SYSTEM_TESTS_PROXY_HOST"]
        elif "DOCKER_HOST" in os.environ:
            m = re.match(r"(?:ssh:|tcp:|fd:|)//(?:[^@]+@|)([^:]+)", os.environ["DOCKER_HOST"])
            domain = m.group(1) if m is not None else "localhost"
        else:
            domain = "localhost"

        response = requests.put(
            f"http://{domain}:{ProxyPorts.proxy_commands}{MOCKED_RESPONSES_PATH}", json=[self.to_json()], timeout=30
        )
        response.raise_for_status()


class StaticJsonMockedResponse(MockedResponse):
    """Always overwrites the same static JSON content on request made on the given path"""

    def __init__(self, path: str, mocked_json: dict | list):
        super().__init__(path=path, mocked_headers={"Content-Type": "application/json"})
        self.mocked_json = mocked_json
        """ Content of the static JSON response """

    def execute(self, flow: HTTPFlow) -> None:
        super().execute(flow)
        flow.response.content = json.dumps(self.mocked_json).encode()

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "path": self.path,
            "mocked_json": self.mocked_json,
        }


class SequentialRemoteConfigJsonMockedResponse(MockedResponse):
    """Overwrites JSON content on request made on /v0.7/config with a sequence of predefined responses"""

    def __init__(self, mocked_json_sequence: list[dict]):
        super().__init__(path="/v0.7/config", mocked_headers={"Content-Type": "application/json"})
        self.mocked_json_sequence = mocked_json_sequence
        """ Sequence of JSON responses to return """

        self._runtime_ids_request_count: dict[str, int] = defaultdict(int)
        """ Tracks how many requests have been made per runtime ID """

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


class _InternalMockedResponse(MockedResponse):
    """Mocked responses that will be applied on the entire test session"""

    def send(self) -> None:
        raise ValueError("This mocked response cannot be sent directly")

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
        }


class AddRemoteConfigEndpoint(_InternalMockedResponse):
    def __init__(self):
        super().__init__(path="/info")

    def execute(self, flow: HTTPFlow) -> None:
        if flow.response.status_code == HTTPStatus.OK:
            content = json.loads(flow.response.content)

            if "/v0.7/config" not in content["endpoints"]:
                content["endpoints"].append("/v0.7/config")
                flow.response.content = json.dumps(content).encode()


class RemoveMetaStructsSupport(_InternalMockedResponse):
    def __init__(self):
        super().__init__(path="/info")

    def execute(self, flow: HTTPFlow) -> None:
        if flow.response.status_code == HTTPStatus.OK:
            c = json.loads(flow.response.content)
            if "span_meta_structs" in c:
                c.pop("span_meta_structs")
                flow.response.content = json.dumps(c).encode()


class SetSpanEventFlags(_InternalMockedResponse):
    """Modify the agent flag that signals support for native span event serialization.
    There are three possible cases:
    - Not configured: agent's response is not modified, the real agent behavior is preserved
    - `true`: agent advertises support for native span events serialization
    - `false`: agent advertises that it does not support native span events serialization
    """

    def __init__(self, *, span_events: bool):
        super().__init__(path="/info")
        self.span_events = span_events
        """ Sequence of boolean values to set the span_events flag to """

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
