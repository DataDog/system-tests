from collections.abc import Generator, Iterable

from utils import interfaces
from utils import remote_config
from utils.dd_constants import RemoteConfigApplyState
from utils.dd_types import DataDogLibrarySpan


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
    states_by_denylist_counts: dict[str, remote_config.RemoteConfigStateResults] = {}

    def setup_scenario(self, blocked_ip_count: int = 12500, blocked_user_count: int = 2500) -> None:
        blocked_ips = [
            f"12.{8 + value // 65536}.{(value // 256) % 256}.{value % 256}" for value in range(blocked_ip_count)
        ]
        denylist_counts = f"{blocked_ip_count}:{blocked_user_count}"

        if denylist_counts not in self.states_by_denylist_counts:
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
                        "data": [
                            {"value": str(value), "expiration": 9999999999} for value in range(blocked_user_count)
                        ],
                    },
                ]
            }

            rc_state = remote_config.tracer_rc_state
            rc_state.set_config("datadog/2/ASM_DATA/ASM_DATA-base/config", config)

            self.states_by_denylist_counts[denylist_counts] = rc_state.apply()

        self.states = self.states_by_denylist_counts[denylist_counts]
        self.blocked_ips = [blocked_ips[0], blocked_ips[-1]]

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
