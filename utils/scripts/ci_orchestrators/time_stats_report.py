import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta
import json
import os
from pathlib import Path
import time as time_module
from typing import Any

import requests


DEFAULT_COMMITTED_PATH = Path("utils/scripts/ci_orchestrators/time-stats.json")
DEFAULT_OUTPUT_DIR = Path("artifacts/ci-viz-time-stats")
DEFAULT_SITE = "datadoghq.com"
MINIMUM_SAMPLE_COUNT = 3
ROW_LIMIT = 10_000
RUN_TIMINGS_QUERY = Path(__file__).with_name("run-time-stats.sql").read_text(encoding="utf-8").strip()


@dataclass(frozen=True)
class TimingRow:
    scenario: str
    library: str
    weblog: str
    sample_count: int
    minimum: float
    median: float
    p75: float
    p95: float
    maximum: float

    @property
    def key(self) -> tuple[str, str, str]:
        return self.scenario, self.library, self.weblog


def _post_json(url: str, auth_headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            **auth_headers,
        },
        json=payload,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Datadog DDSQL request failed with HTTP {response.status_code}")
    return response.json()


def query_ddsql(
    *,
    query: str,
    from_time: datetime,
    to_time: datetime,
    auth_headers: dict[str, str],
    site: str,
) -> dict[str, Any]:
    base_url = f"https://api.{site}/api/v2/ddsql/query/tabular"
    response = _post_json(
        base_url,
        auth_headers,
        {
            "data": {
                "attributes": {
                    "query": query,
                    "row_limit": ROW_LIMIT,
                    "time": {
                        "from_timestamp": int(from_time.timestamp() * 1000),
                        "to_timestamp": int(to_time.timestamp() * 1000),
                    },
                },
                "type": "ddsql_query_request",
            }
        },
    )

    for _attempt in range(60):
        attributes = response["data"]["attributes"]
        if attributes["state"] == "completed":
            return response
        if attributes["state"] != "running":
            raise RuntimeError(f"Unexpected DDSQL query state: {attributes['state']}")

        time_module.sleep(1)
        response = _post_json(
            f"{base_url}/fetch",
            auth_headers,
            {
                "data": {
                    "attributes": {"query_id": attributes["query_id"]},
                    "type": "ddsql_query_fetch_request",
                }
            },
        )

    raise TimeoutError("DDSQL query did not complete within 60 seconds")


def rows_from_ddsql(response: dict[str, Any]) -> list[TimingRow]:
    attributes = response["data"]["attributes"]
    warnings = attributes.get("warnings", [])
    if any("truncat" in warning.lower() for warning in warnings):
        raise RuntimeError(f"DDSQL result was truncated: {warnings}")

    columns = attributes.get("columns", [])
    if not columns:
        raise RuntimeError("DDSQL query returned no columns")

    values_by_name = {column["name"]: column["values"] for column in columns}
    expected_columns = set(TimingRow.__dataclass_fields__)
    if set(values_by_name) != expected_columns:
        raise RuntimeError(
            f"Unexpected DDSQL columns: expected {sorted(expected_columns)}, got {sorted(values_by_name)}"
        )

    lengths = {len(values) for values in values_by_name.values()}
    if len(lengths) != 1:
        raise RuntimeError("DDSQL columns have inconsistent lengths")

    row_count = lengths.pop()
    if row_count == 0:
        raise RuntimeError("DDSQL query returned no timing rows")

    return [
        TimingRow(
            scenario=str(values_by_name["scenario"][index]),
            library=str(values_by_name["library"][index]),
            weblog=str(values_by_name["weblog"][index]),
            sample_count=int(values_by_name["sample_count"][index]),
            minimum=float(values_by_name["minimum"][index]),
            median=float(values_by_name["median"][index]),
            p75=float(values_by_name["p75"][index]),
            p95=float(values_by_name["p95"][index]),
            maximum=float(values_by_name["maximum"][index]),
        )
        for index in range(row_count)
    ]


def load_input(path: Path) -> list[TimingRow]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return [TimingRow(**row) for row in data]
    return rows_from_ddsql(data)


def get_auth_headers(environ: dict[str, str]) -> dict[str, str]:
    if bearer_token := environ.get("DD_BEARER_TOKEN"):
        return {"Authorization": f"Bearer {bearer_token}"}

    api_key = environ.get("DD_API_KEY")
    application_key = environ.get("DD_APPLICATION_KEY") or environ.get("DD_APP_KEY")
    if api_key and application_key:
        return {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": application_key}

    raise RuntimeError("Set DD_BEARER_TOKEN or both DD_API_KEY and DD_APPLICATION_KEY to query CI Viz")


def load_committed_timings(path: Path) -> dict[tuple[str, str, str], float]:
    with path.open(encoding="utf-8") as file:
        committed = json.load(file)

    result: dict[tuple[str, str, str], float] = {}
    for scenario, libraries in committed["run"].items():
        if scenario == "*":
            continue
        for library, weblogs in libraries.items():
            if library == "*":
                continue
            for weblog, duration in weblogs.items():
                if weblog != "*":
                    result[(scenario, library, weblog)] = float(duration)
    return result


def build_computed_timings(rows: list[TimingRow]) -> dict[str, Any]:
    run: dict[str, Any] = {}
    for row in sorted(rows, key=lambda item: item.key):
        run.setdefault(row.scenario, {}).setdefault(row.library, {})[row.weblog] = row.p75

    for libraries in run.values():
        library_averages = []
        for weblogs in libraries.values():
            values = list(weblogs.values())
            weblogs["*"] = sum(values) / len(values)
            library_averages.append(weblogs["*"])
        libraries["*"] = sum(library_averages) / len(library_averages)

    scenario_averages = [libraries["*"] for libraries in run.values()]
    run["*"] = sum(scenario_averages) / len(scenario_averages)
    return {"run": run}


def compare_timings(rows: list[TimingRow], committed: dict[tuple[str, str, str], float]) -> dict[str, Any]:
    computed = {row.key: row for row in rows}
    changes = []
    for key in sorted(computed.keys() & committed.keys()):
        row = computed[key]
        current = committed[key]
        delta = row.p75 - current
        changes.append(
            {
                "scenario": row.scenario,
                "library": row.library,
                "weblog": row.weblog,
                "sample_count": row.sample_count,
                "current": current,
                "computed_p75": row.p75,
                "delta": delta,
                "delta_percent": delta / current * 100 if current else None,
                "minimum": row.minimum,
                "median": row.median,
                "p95": row.p95,
                "maximum": row.maximum,
            }
        )

    added = [asdict(computed[key]) for key in sorted(computed.keys() - committed.keys())]
    missing = [
        {"scenario": key[0], "library": key[1], "weblog": key[2], "current": committed[key]}
        for key in sorted(committed.keys() - computed.keys())
    ]
    low_samples = [asdict(row) for row in rows if row.sample_count < MINIMUM_SAMPLE_COUNT]

    return {
        "summary": {
            "computed": len(computed),
            "committed": len(committed),
            "compared": len(changes),
            "added": len(added),
            "missing": len(missing),
            "low_samples": len(low_samples),
        },
        "changes": changes,
        "added": added,
        "missing": missing,
        "low_samples": low_samples,
    }


def render_report(comparison: dict[str, Any], from_time: datetime, to_time: datetime) -> str:
    summary = comparison["summary"]
    lines = [
        "# CI Viz timing report",
        "",
        f"Window: `{from_time.isoformat()}` to `{to_time.isoformat()}`",
        "",
        "## Coverage",
        "",
        "| Computed | Committed | Compared | Added | Missing | Low samples |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {summary['computed']} | {summary['committed']} | {summary['compared']} | "
            f"{summary['added']} | {summary['missing']} | {summary['low_samples']} |"
        ),
        "",
        "## Largest p75 changes",
        "",
        "| Scenario | Library | Weblog | Samples | Current | Computed p75 | Delta | Delta % | p50 | p95 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    changes = sorted(
        comparison["changes"],
        key=lambda change: abs(change["delta_percent"] or 0),
        reverse=True,
    )
    for change in changes[:50]:
        delta_percent = change["delta_percent"]
        delta_percent_text = "n/a" if delta_percent is None else f"{delta_percent:+.1f}%"
        lines.append(
            f"| {change['scenario']} | {change['library']} | {change['weblog']} | "
            f"{change['sample_count']} | {change['current']:.1f} | {change['computed_p75']:.1f} | "
            f"{change['delta']:+.1f} | {delta_percent_text} | {change['median']:.1f} | {change['p95']:.1f} |"
        )

    _append_key_section(lines, "New CI Viz combinations", comparison["added"])
    _append_key_section(lines, "Committed combinations missing from CI Viz", comparison["missing"])
    _append_key_section(lines, "Combinations below the sample threshold", comparison["low_samples"])
    return "\n".join(lines) + "\n"


def _append_key_section(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.extend(["", f"## {title}", ""])
    if not rows:
        lines.append("None.")
        return

    lines.extend(["| Scenario | Library | Weblog |", "| --- | --- | --- |"])
    for row in rows[:100]:
        lines.append(f"| {row['scenario']} | {row['library']} | {row['weblog']} |")


def write_json(path: Path, data: object) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True, allow_nan=False)
        file.write("\n")


def default_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    to_time = datetime.combine(current.date(), time.min, tzinfo=UTC)
    return to_time - timedelta(days=7), to_time


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_args() -> argparse.Namespace:
    window_start, window_end = default_window()
    parser = argparse.ArgumentParser(description="Compute and compare CI Viz run timings")
    parser.add_argument(
        "--input",
        type=Path,
        help="Read aggregate rows or a DDSQL response instead of querying Datadog",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--committed", type=Path, default=DEFAULT_COMMITTED_PATH)
    parser.add_argument("--from", dest="from_time", type=parse_datetime, default=window_start)
    parser.add_argument("--to", dest="to_time", type=parse_datetime, default=window_end)
    parser.add_argument("--site", default=os.environ.get("DD_SITE", DEFAULT_SITE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.from_time >= args.to_time:
        raise ValueError("--from must be earlier than --to")

    if args.input:
        rows = load_input(args.input)
        source = str(args.input)
    else:
        response = query_ddsql(
            query=RUN_TIMINGS_QUERY,
            from_time=args.from_time,
            to_time=args.to_time,
            auth_headers=get_auth_headers(dict(os.environ)),
            site=args.site,
        )
        rows = rows_from_ddsql(response)
        source = f"DDSQL at {args.site}"

    if not rows:
        raise RuntimeError("No timing rows were provided")

    committed = load_committed_timings(args.committed)
    comparison = compare_timings(rows, committed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_json(args.output_dir / "run-distribution.json", [asdict(row) for row in rows])
    write_json(args.output_dir / "computed-run-timings.json", build_computed_timings(rows))
    write_json(args.output_dir / "comparison.json", comparison)
    write_json(
        args.output_dir / "metadata.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "from": args.from_time.isoformat(),
            "to": args.to_time.isoformat(),
            "source": source,
            "query": "run timings",
            "row_count": len(rows),
            "minimum_sample_count": MINIMUM_SAMPLE_COUNT,
        },
    )
    (args.output_dir / "run-timings.sql").write_text(RUN_TIMINGS_QUERY + "\n", encoding="utf-8")
    (args.output_dir / "comparison.md").write_text(
        render_report(comparison, args.from_time, args.to_time),
        encoding="utf-8",
    )

    print(f"Wrote CI Viz timing report to {args.output_dir}")


if __name__ == "__main__":
    main()
