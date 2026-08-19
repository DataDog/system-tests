from collections.abc import Generator, Iterable
import os

from utils import interfaces
from utils import remote_config
from utils.dd_constants import RemoteConfigApplyState
from utils.dd_types import DataDogLibrarySpan

BLOCKED_IPS_COUNT_ENV_VAR = "SYSTEM_TESTS_BLOCKED_IPS_COUNT"
DEFAULT_BLOCKED_IPS_COUNT = 12500
# _blocked_ip() lays the denylist out over 12.8.0.0-12.9.255.255, using the second octet as an
# overflow digit for the two low ones. That range holds 2 * 65536 = 131072 addresses, so raising
# this limit any further means picking a wider IP range first.
MAX_BLOCKED_IPS_COUNT = 100000


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


def _get_blocked_ips_count() -> int:
    """Size of the IP denylist sent through remote config, overridable to probe other library limits."""
    raw_count = os.environ.get(BLOCKED_IPS_COUNT_ENV_VAR, str(DEFAULT_BLOCKED_IPS_COUNT))

    try:
        count = int(raw_count)
    except ValueError as error:
        raise ValueError(f"{BLOCKED_IPS_COUNT_ENV_VAR} must be an integer, got {raw_count!r}") from error

    if not 1 <= count <= MAX_BLOCKED_IPS_COUNT:
        raise ValueError(f"{BLOCKED_IPS_COUNT_ENV_VAR} must be between 1 and {MAX_BLOCKED_IPS_COUNT}, got {count}")

    return count


def _blocked_ip(index: int) -> str:
    """Address at the given position of the denylist. The denylist is contiguous, so an index
    fully determines an address, and only the sampled ones need to be materialized.
    """
    return f"12.{8 + index // 65536}.{index // 256 % 256}.{index % 256}"


class BaseFullDenyListTest:
    states: remote_config.RemoteConfigStateResults | None = None

    def setup_scenario(self) -> None:
        blocked_ips_count = _get_blocked_ips_count()

        if BaseFullDenyListTest.states is None:
            config = {
                "rules_data": [
                    {
                        "id": "blocked_ips",
                        "type": "ip_with_expiration",
                        "data": [
                            {"value": _blocked_ip(index), "expiration": 9999999999}
                            for index in range(blocked_ips_count)
                        ],
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
        # first, middle and last entries. The last one carries the test: libraries have
        # historically truncated the tail of an oversized denylist.
        sample_indices = sorted({0, blocked_ips_count // 2, blocked_ips_count - 1})
        self.blocked_ips = [_blocked_ip(index) for index in sample_indices]

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
