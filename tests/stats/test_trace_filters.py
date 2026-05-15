from typing import Any

from utils import features, interfaces, logger, scenarios, weblog


def _wait_for_trace_filters() -> None:
    def wait_function(data: dict[str, Any]) -> bool:
        content = data.get("response", {}).get("content", {})
        return (
            data.get("path") == "/info"
            and isinstance(content, dict)
            and any(key in content for key in ("filter_tags", "filter_tags_regex", "ignore_resources"))
        )

    interfaces.library.wait_for(wait_function, 30)
    assert any(wait_function(data) for data in interfaces.library.get_data("/info")), (
        "Expected the tracer to receive trace filter configuration from /info"
    )


def _client_stats() -> list[dict[str, Any]]:
    stats: list[dict[str, Any]] = []
    for data in interfaces.library.get_data("/v0.6/stats"):
        payload = data["request"]["content"]
        for bucket in payload.get("Stats", []):
            stats.extend(bucket.get("Stats", []))

    logger.debug(f"Client stats observed for trace filters: {stats}")
    return stats


def _stats_with_http_status(status_code: int) -> list[dict[str, Any]]:
    return [stat for stat in _client_stats() if stat.get("HTTPStatusCode") == status_code]


def _observed_status_codes() -> list[int]:
    return sorted(
        {
            stat["HTTPStatusCode"]
            for stat in _client_stats()
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
        _wait_for_trace_filters()
        weblog.get("/stats-unique?code=203")

    def test_ignore_resources(self) -> None:
        _assert_status_absent(203)

    def setup_filter_tags_reject(self) -> None:
        _wait_for_trace_filters()
        weblog.get("/tag_value/tf-reject-exact/206")

    def test_filter_tags_reject(self) -> None:
        _assert_status_absent(206)

    def setup_filter_tags_regex_reject(self) -> None:
        _wait_for_trace_filters()
        weblog.get("/tag_value/tf-reject-regex-hit/207")

    def test_filter_tags_regex_reject(self) -> None:
        _assert_status_absent(207)

    def setup_trace_not_matching_reject_filters(self) -> None:
        _wait_for_trace_filters()
        weblog.get("/tag_value/tf-keep/208")

    def test_trace_not_matching_reject_filters(self) -> None:
        _assert_status_present(208)


@features.client_side_stats_supported
@scenarios.trace_stats_computation_trace_filter_require
class Test_Trace_Filters_Require:
    def setup_trace_matching_required_filters(self) -> None:
        _wait_for_trace_filters()
        weblog.get("/tag_value/tf-required/207")

    def test_trace_matching_required_filters(self) -> None:
        _assert_status_present(207)

    def setup_filter_tags_require(self) -> None:
        _wait_for_trace_filters()
        weblog.get("/tag_value/tf-wrong/208")

    def test_filter_tags_require(self) -> None:
        _assert_status_absent(208)

    def setup_filter_tags_regex_require(self) -> None:
        _wait_for_trace_filters()
        weblog.get("/tag_value/tf-required/418")

    def test_filter_tags_regex_require(self) -> None:
        _assert_status_absent(418)
