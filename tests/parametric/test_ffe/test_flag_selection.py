"""Server SDK flag selection against the mocked FFE agentless backend.

Feature under test: a server SDK given a flag selection sends it on the agentless configuration request and serves
only the flags the backend returns. The mocked backend applies the selection to the shared ufc-config.json with the
shared tags in flag-selection/ufc-config-tags.json.
"""

import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from utils import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import EXPECTED_DD_ENV, SELECTED_FLAG_TAGS


@pytest.fixture
def library_env(mocked_backend: MockedBackendServer) -> dict[str, str]:
    mocked_backend.client.ffe_set_response("valid")
    return {
        "DD_API_KEY": scenarios.parametric.dd_api_key,
        "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "agentless",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": mocked_backend.ffe_library_config_url,
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "1",
    }


def _evaluate_boolean(test_library: APMLibrary, flag: str) -> dict[str, Any]:
    for _ in range(10):
        result = test_library.ffe_evaluate(
            flag=flag, variation_type="BOOLEAN", default_value=False, targeting_key="alice", attributes={}
        )
        if result.get("errorCode") != "PROVIDER_NOT_READY":
            break
        time.sleep(0.2)
    return result


@scenarios.parametric
@features.feature_flags_configuration_filtering
class Test_FFE_Flag_Selection:
    def test_tag_selection_loads_only_selected_flags(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        assert test_library.ffe_start({"flagSelection": {"tags": [" team:checkout ", "team:checkout"]}})

        selected = _evaluate_boolean(test_library, "basic-flag")
        requests = mocked_backend.ffe_get_requests()
        assert requests, "the SDK did not fetch its configuration"
        assert parse_qs(urlsplit(requests[0]["path"]).query, keep_blank_values=True) == {
            "dd_env": [EXPECTED_DD_ENV],
            SELECTED_FLAG_TAGS: ["team:checkout"],
        }, "the configuration request does not carry the canonical selection"
        assert selected.get("value") is True, selected

        unselected = _evaluate_boolean(test_library, "serial-id-basic-flag")
        assert unselected.get("value") is False, unselected
        assert unselected.get("errorCode") == "FLAG_NOT_FOUND", unselected
