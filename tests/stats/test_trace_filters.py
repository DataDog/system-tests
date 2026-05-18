from typing import Any

from utils import features, interfaces, logger, scenarios, weblog

"""
Each test does in sequence:
    * Setup:
        - Send the request we want to test a trace filter on
        - Send a control request that will always pass the filters
        - Wait for the control request to be sent by the client (on stats flush so ~30s later)
    * Test
        - Check if the filtered request is present in client sent stats or not

Config:
- apm_config.filter_tags.reject
- apm_config.filter_tags.require
- apm_config.filter_tags_regex.reject
- apm_config.filter_tags_regex.require
- apm_config.ignore_resources
"""


def _library_stats() -> list[dict[str, Any]]:
    stats: list[dict[str, Any]] = []
    for data in interfaces.library.get_data("/v0.6/stats"):
        payload = data["request"]["content"]
        for bucket in payload.get("Stats", []):
            stats.extend(bucket.get("Stats", []))

    logger.debug(f"Library stats observed for trace filters: {stats}")
    return stats


def _stats_with_http_status(status_code: int) -> list[dict[str, Any]]:
    return [stat for stat in _library_stats() if stat.get("HTTPStatusCode") == status_code]


def _wait_for_stats_with_http_status(status_code: int) -> None:
    def wait_function(data: dict[str, Any]) -> bool:
        if data.get("path") != "/v0.6/stats":
            return False

        payload = data.get("request", {}).get("content", {})
        return any(
            stat.get("HTTPStatusCode") == status_code
            for bucket in payload.get("Stats", [])
            for stat in bucket.get("Stats", [])
        )

    interfaces.library.wait_for(wait_function, 30)
    _assert_status_present(status_code)


def _observed_status_codes() -> list[int]:
    return sorted(
        {
            stat["HTTPStatusCode"]
            for stat in _library_stats()
            if isinstance(stat.get("HTTPStatusCode"), int) and stat.get("HTTPStatusCode") != 0
        }
    )


def _assert_status_absent(status_code: int) -> None:
    matching_stats = _stats_with_http_status(status_code)
    assert not matching_stats, (
        f"Expected no client stats for HTTP status {status_code}, "
        f"got {matching_stats}. Observed status codes: {_observed_status_codes()}"
    )


def _assert_status_present(status_code: int) -> None:
    matching_stats = _stats_with_http_status(status_code)
    assert matching_stats, (
        f"Expected client stats for HTTP status {status_code}. Observed status codes: {_observed_status_codes()}"
    )


@features.client_side_stats_supported
@scenarios.trace_stats_computation_trace_filter_reject
class Test_Trace_Filters_Reject:
    def setup_ignore_resources(self) -> None:
        weblog.get("/stats-unique?code=203")
        weblog.get("/tag_value/tf-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_ignore_resources(self) -> None:
        # Because resource matches the ignore_resources pattern ".*(stats-unique|StatsUniqueHandler).*"
        _assert_status_absent(203)

    def setup_filter_tags_reject(self) -> None:
        weblog.get("/tag_value/tf-reject-exact/206")
        weblog.get("/tag_value/tf-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_filter_tags_reject(self) -> None:
        # Because the reject tag "appsec.events.system_tests_appsec_event.value:tf-reject-exact" is present
        _assert_status_absent(206)

    def setup_filter_tags_regex_reject(self) -> None:
        weblog.get("/tag_value/tf-reject-regex-hit/207")
        weblog.get("/tag_value/tf-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_filter_tags_regex_reject(self) -> None:
        # Because the reject tag regex "appsec.events.system_tests_appsec_event.value:tf-reject-regex-.*" matches its value "tf-reject-regex-hit"
        _assert_status_absent(207)

    def setup_trace_not_matching_reject_filters(self) -> None:
        weblog.get("/tag_value/tf-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_trace_not_matching_reject_filters(self) -> None:
        # Because it doesn't match any of the reject filter/ignore_resouces
        _assert_status_present(208)


@features.client_side_stats_supported
@scenarios.trace_stats_computation_trace_filter_require
class Test_Trace_Filters_Require:
    def setup_trace_matching_required_filters(self) -> None:
        weblog.get("/tag_value/tf-required/207")
        _wait_for_stats_with_http_status(207)

    def test_trace_matching_required_filters(self) -> None:
        # Because:
        #   - 207 (http.status_code) does matches the pattern 20[78]
        #   - "appsec.events.system_tests_appsec_event.value:tf-required" tag is present
        _assert_status_present(207)

    def setup_filter_tags_require(self) -> None:
        weblog.get("/tag_value/tf-wrong/208")
        weblog.get("/tag_value/tf-required/207")
        _wait_for_stats_with_http_status(207)

    def test_filter_tags_require(self) -> None:
        # Because the "appsec.events.system_tests_appsec_event.value:tf-required" required tag is absent
        _assert_status_absent(208)

    def setup_filter_tags_regex_require(self) -> None:
        weblog.get("/tag_value/tf-required/418")
        weblog.get("/tag_value/tf-required/207")
        _wait_for_stats_with_http_status(207)

    def test_filter_tags_regex_require(self) -> None:
        # Because 418 (http.status_code) does not match the pattern 20[78]
        _assert_status_absent(418)
