"""Client of the mocked backend control endpoints, used by tests and scenarios. It only needs the base URL
of the server, so it works the same whether the server runs in the test process or in a container.
"""

from __future__ import annotations

from typing import cast

import requests

from ._backend_ffe import MockedBackendFFEStatus, validate_responses
from ._utils import CONTROL_URL_PREFIX

_FFE_CONTROL_PATH = f"{CONTROL_URL_PREFIX}/ffe"


class MockedBackendClient:
    def __init__(self, base_url: str, *, verify: bool | str = True) -> None:
        """verify: as in requests, e.g. the CA file trusting the certificate of an HTTPS server"""
        self.base_url = base_url.rstrip("/")
        self.verify = verify

    def ffe_reset(self) -> None:
        response = requests.post(f"{self.base_url}{_FFE_CONTROL_PATH}/reset", timeout=5, verify=self.verify)
        response.raise_for_status()

    def ffe_set_response(self, response_id: str) -> None:
        self.ffe_set_responses([response_id])

    def ffe_set_responses(self, responses: object) -> None:
        validated_responses = validate_responses(responses)
        response = requests.post(
            f"{self.base_url}{_FFE_CONTROL_PATH}/responses",
            json={"responses": validated_responses},
            timeout=5,
            verify=self.verify,
        )
        response.raise_for_status()

    def ffe_get_status(self) -> MockedBackendFFEStatus:
        response = requests.get(f"{self.base_url}{_FFE_CONTROL_PATH}/status", timeout=5, verify=self.verify)
        response.raise_for_status()
        return cast("MockedBackendFFEStatus", response.json())
