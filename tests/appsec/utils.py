from collections.abc import Generator, Iterable
import os

from utils import interfaces
from utils import remote_config
from utils.dd_constants import RemoteConfigApplyState
from utils.dd_types import DataDogLibrarySpan

try:
    BLOCKED_IP_COUNT = int(os.environ.get("SYSTEM_TESTS_BLOCKED_IPS_COUNT", "12500"))
except ValueError as error:
    raise ValueError("SYSTEM_TESTS_BLOCKED_IPS_COUNT must be an integer") from error

if not 1 <= BLOCKED_IP_COUNT <= 100000:
    raise ValueError("SYSTEM_TESTS_BLOCKED_IPS_COUNT must be between 1 and 100000")


def assert_all_spans_have_apm_disabled_marker(spans: Iterable[DataDogLibrarySpan]) -> None:
    span_list = list(spans)
    assert span_list, "No spans were sent for the request"

    for span in span_list:
        apm_enabled = span["metrics"].get("_dd.apm.enabled")
        error_message = f"Span is missing numeric _dd.apm.enabled:0: {span.raw_span}"
        assert isinstance(apm_enabled, (int, float)), error_message
        assert not isinstance(apm_enabled, bool), error_message
        assert apm_enabled == 0, error_message


def find_series(namespace: str, metrics: list[str]) -> list:
    series = []
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") != "generate-metrics":
            continue
        payload = content["payload"]
        fallback_namespace = payload.get("namespace")
        for serie in payload["series"]:
            computed_namespace = serie.get("namespace", fallback_namespace)
            if computed_namespace == namespace and serie["metric"] in metrics:
                series.append(serie)
    return series


def find_configuration() -> Generator:
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") not in ["app-started", "app-client-configuration-change"]:
            continue
        payload = content["payload"]
        yield payload.get("configuration")


class BaseFullDenyListTest:
    states: remote_config.RemoteConfigStateResults | None = None

    def setup_scenario(self) -> None:
        blocked_ips = [
            f"12.{8 + value // 65536}.{(value // 256) % 256}.{value % 256}" for value in range(BLOCKED_IP_COUNT)
        ]

        if BaseFullDenyListTest.states is None:
            config = {
                "rules_data": [
                    {
                        "id": "blocked_ips",
                        "type": "ip_with_expiration",
                        "data": [{"value": ip, "expiration": 9999999999} for ip in blocked_ips],
                    },
                    {
                        "id": "blocked_users",
                        "type": "data_with_expiration",
                        "data": [{"value": str(value), "expiration": 9999999999} for value in range(2500)],
                    },
                ]
            }

            rc_state = remote_config.tracer_rc_state
            rc_state.set_config("datadog/2/ASM_DATA/ASM_DATA-base/config", config)

            BaseFullDenyListTest.states = rc_state.apply()

        self.states = BaseFullDenyListTest.states
        sample_indices = sorted({0, BLOCKED_IP_COUNT // 2, BLOCKED_IP_COUNT - 1})
        self.blocked_ips = [blocked_ips[index] for index in sample_indices]

    def assert_protocol_is_respected(self) -> None:
        assert self.states is not None
        interfaces.library.assert_rc_targets_version_states(targets_version=0, config_states=[])
        interfaces.library.assert_rc_targets_version_states(
            targets_version=self.states.version,
            config_states=[
                {
                    "id": "ASM_DATA-base",
                    "version": 1,
                    "product": "ASM_DATA",
                    "apply_state": RemoteConfigApplyState.ACKNOWLEDGED.value,
                }
            ],
        )
