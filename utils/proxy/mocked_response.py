import json
import os
import re
import requests

from mitmproxy.http import HTTPFlow

from .ports import ProxyPorts, MOCKED_RESPONSE_PATH


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

    @staticmethod
    def build_from_json(source: dict) -> "MockedResponse":
        """Factory to create the right MockedResponse subclass from json data"""
        mocked_response_type = source.pop("type")

        if mocked_response_type == StaticJsonMockedResponse.__name__:
            return StaticJsonMockedResponse.from_json(source)
        if mocked_response_type == MockedResponse.__name__:
            return MockedResponse.from_json(source)

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
            f"http://{domain}:{ProxyPorts.proxy_commands}{MOCKED_RESPONSE_PATH}", json=self.to_json(), timeout=30
        )
        response.raise_for_status()


class StaticJsonMockedResponse(MockedResponse):
    """Always overwrites the same static JSON content on request made on the given path"""

    def __init__(self, path: str, mocked_json: dict | list):
        super().__init__(path=path, mocked_headers={"Content-Type": "application/json"})
        self.mocked_json = mocked_json
        """ Content of the static JSON response """

    def __str__(self):
        return f"<{self.__class__.__name__} path={self.path}>"

    def execute(self, flow: HTTPFlow) -> None:
        super().execute(flow)
        flow.response.content = json.dumps(self.mocked_json).encode("utf-8")

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "path": self.path,
            "mocked_json": self.mocked_json,
        }
