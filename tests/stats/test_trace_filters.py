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


@features.client_side_stats_supported
@scenarios.trace_stats_computation_trace_filter_reject_edge_cases
class Test_Trace_Filters_Reject_Edge_Cases:
    """
    Filter config (see scenario):
      filter_tags.reject:       [" key : tf-trim ", ":tf-no-key"]
      filter_tags_regex.reject: [" key : tf-regex-trim.* ", "key:[invalid"]
    """

    def setup_literal_whitespace_trim_drops(self) -> None:
        weblog.get("/tag_value/tf-trim/221")
        weblog.get("/tag_value/tf-edge-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_literal_whitespace_trim_drops(self) -> None:
        # Filter " key : tf-trim " has spaces around colon; after trimming it equals "key:tf-trim"
        # and must still reject the trace.
        _assert_status_absent(221)

    def setup_empty_key_skipped_keeps(self) -> None:
        weblog.get("/tag_value/tf-no-key/222")
        weblog.get("/tag_value/tf-edge-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_empty_key_skipped_keeps(self) -> None:
        # Filter ":tf-no-key" has an empty key; it is silently skipped so the trace is kept.
        _assert_status_present(222)

    def setup_regex_whitespace_trim_drops(self) -> None:
        weblog.get("/tag_value/tf-regex-trim-x/223")
        weblog.get("/tag_value/tf-edge-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_regex_whitespace_trim_drops(self) -> None:
        # Regex filter " key : tf-regex-trim.* " has spaces; after trimming the regex still matches.
        _assert_status_absent(223)

    def setup_bad_regex_skipped_keeps(self) -> None:
        weblog.get("/tag_value/tf-bad-regex/224")
        weblog.get("/tag_value/tf-edge-keep/208")
        _wait_for_stats_with_http_status(208)

    def test_bad_regex_skipped_keeps(self) -> None:
        # Filter "key:[invalid" is an invalid regex; it is silently dropped so the trace is kept.
        _assert_status_present(224)


@features.client_side_stats_supported
@scenarios.trace_stats_computation_trace_filter_key_only_reject
class Test_Trace_Filters_Key_Only_Reject:
    """
    Filter config (see scenario):
      filter_tags.reject: ["appsec.events.system_tests_appsec_event.value"]  (key only, no value)

    /stats-unique is used as control because /tag_value/* would also be rejected by the key-only filter.
    """

    def setup_key_only_reject_drops_any_value(self) -> None:
        weblog.get("/tag_value/anything/229")
        weblog.get("/stats-unique?code=228")
        _wait_for_stats_with_http_status(228)

    def test_key_only_reject_drops_any_value(self) -> None:
        # A key-only filter (no value part) must reject any span that has the tag, whatever the value.
        _assert_status_absent(229)

    def test_no_tag_not_dropped(self) -> None:
        # Traces without the tag are not affected by the key-only reject filter.
        _assert_status_present(228)


@features.client_side_stats_supported
@scenarios.trace_stats_computation_trace_filter_require_edge_cases
class Test_Trace_Filters_Require_Edge_Cases:
    """
    Filter config (see scenario):
      filter_tags.require:       [" key : tf-req-trim "]   (trimmed: exact value "tf-req-trim")
      filter_tags_regex.require: [" key : tf-req.* "]      (trimmed: regex matches "tf-req.*")

    Both filters are simultaneously satisfiable: value "tf-req-trim" matches the literal exactly
    and also matches the regex tf-req.*. Tests verify whitespace trimming works for both literal
    and regex require filters.
    """

    def setup_whitespace_trim_require_keeps(self) -> None:
        weblog.get("/tag_value/tf-req-trim/231")
        _wait_for_stats_with_http_status(231)

    def test_whitespace_trim_require_keeps(self) -> None:
        # Value "tf-req-trim" satisfies both trimmed filters (" key : tf-req-trim " and
        # " key : tf-req.* "), so the trace must be kept.
        _assert_status_present(231)

    def setup_whitespace_trim_require_drops(self) -> None:
        weblog.get("/tag_value/tf-wrong/232")
        weblog.get("/tag_value/tf-req-trim/231")
        _wait_for_stats_with_http_status(231)

    def test_whitespace_trim_require_drops(self) -> None:
        # Value "tf-wrong" satisfies neither trimmed filter, so the trace must be dropped.
        _assert_status_absent(232)
