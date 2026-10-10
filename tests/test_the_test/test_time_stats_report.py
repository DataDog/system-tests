from datetime import UTC, datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "utils/scripts/ci_orchestrators"))

from time_stats_report import (
    TimingRow,
    build_computed_timings,
    compare_timings,
    default_window,
    get_auth_headers,
    render_report,
    rows_from_ddsql,
)

pytestmark = pytest.mark.scenario("TEST_THE_TEST")


def timing_row(
    scenario: str = "APPSEC_API_SECURITY",
    library: str = "ruby",
    weblog: str = "rails72",
    sample_count: int = 7,
    p75: float = 42,
) -> TimingRow:
    return TimingRow(
        scenario=scenario,
        library=library,
        weblog=weblog,
        sample_count=sample_count,
        minimum=35,
        median=39,
        p75=p75,
        p95=48,
        maximum=50,
    )


def test_rows_from_ddsql_decodes_column_major_response():
    row = timing_row()
    response = {
        "data": {
            "attributes": {
                "state": "completed",
                "columns": [{"name": name, "values": [value]} for name, value in row.__dict__.items()],
            }
        }
    }

    assert rows_from_ddsql(response) == [row]


def test_rows_from_ddsql_rejects_truncated_results():
    response = {"data": {"attributes": {"state": "completed", "warnings": ["Result was truncated"]}}}

    with pytest.raises(RuntimeError, match="truncated"):
        rows_from_ddsql(response)


def test_get_auth_headers_prefers_bearer_token():
    headers = get_auth_headers(
        {
            "DD_BEARER_TOKEN": "bearer-token",
            "DD_API_KEY": "api-key",
            "DD_APPLICATION_KEY": "application-key",
        }
    )

    assert headers == {"Authorization": "Bearer bearer-token"}


def test_get_auth_headers_supports_existing_api_and_application_keys():
    headers = get_auth_headers({"DD_API_KEY": "api-key", "DD_APPLICATION_KEY": "application-key"})

    assert headers == {"DD-API-KEY": "api-key", "DD-APPLICATION-KEY": "application-key"}


def test_build_computed_timings_recomputes_fallbacks():
    rows = [
        timing_row(weblog="rails72", p75=40),
        timing_row(weblog="sinatra41", p75=50),
        timing_row(library="python", weblog="flask-poc", p75=90),
    ]

    result = build_computed_timings(rows)

    assert result["run"]["APPSEC_API_SECURITY"]["ruby"]["*"] == 45
    assert result["run"]["APPSEC_API_SECURITY"]["python"]["*"] == 90
    assert result["run"]["APPSEC_API_SECURITY"]["*"] == 67.5
    assert result["run"]["*"] == 67.5


def test_compare_timings_reports_changes_additions_missing_and_low_samples():
    rows = [
        timing_row(p75=42),
        timing_row(scenario="NEW_SCENARIO", weblog="rack", sample_count=2, p75=10),
    ]
    committed = {
        ("APPSEC_API_SECURITY", "ruby", "rails72"): 30,
        ("MISSING_SCENARIO", "ruby", "rack"): 20,
    }

    result = compare_timings(rows, committed)

    assert result["summary"] == {
        "computed": 2,
        "committed": 2,
        "compared": 1,
        "added": 1,
        "missing": 1,
        "low_samples": 1,
    }
    assert result["changes"][0]["delta"] == 12
    assert result["changes"][0]["delta_percent"] == 40
    assert result["added"][0]["scenario"] == "NEW_SCENARIO"
    assert result["missing"][0]["scenario"] == "MISSING_SCENARIO"


def test_render_report_contains_summary_and_distribution():
    rows = [timing_row(p75=42)]
    comparison = compare_timings(rows, {rows[0].key: 30})

    report = render_report(
        comparison,
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 10, 8, tzinfo=UTC),
    )

    assert "| 1 | 1 | 1 | 0 | 0 | 0 |" in report
    assert "| APPSEC_API_SECURITY | ruby | rails72 | 7 | 30.0 | 42.0 |" in report


def test_default_window_uses_seven_complete_utc_days():
    start, end = default_window(datetime(2026, 10, 9, 12, 30, tzinfo=UTC))

    assert start == datetime(2026, 10, 2, tzinfo=UTC)
    assert end == datetime(2026, 10, 9, tzinfo=UTC)
