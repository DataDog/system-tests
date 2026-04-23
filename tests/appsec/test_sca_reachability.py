"""Tests for SCA Runtime Reachability feature.

When DD_APPSEC_SCA_ENABLED=true, the tracer reports CVE metadata on vulnerable
dependencies via telemetry app-dependencies-loaded events. When a vulnerable
function is called, caller information is added to the reached array.

RFC: https://docs.google.com/document/d/1xDw9iG6h41VCEgJGTqoJdruRaNS4pYgNifO6nhiizWA/edit
"""

import json
from typing import Any

from utils import weblog, interfaces, scenarios, features, rfc, context

SCA_REACHABILITY_RFC = "https://docs.google.com/document/d/1xDw9iG6h41VCEgJGTqoJdruRaNS4pYgNifO6nhiizWA/edit"

# Per-language expected values for SCA reachability tests.
# Only populate entries once the language's tracer supports SCA reachability
# and the expected values are confirmed. Missing languages gracefully
# degrade: structural assertions still run, but value comparisons are skipped.
_LANG_CONFIG: dict[str, dict[str, str]] = {
    "python": {
        "cve_id": "CVE-2024-35195",
        "vulnerable_dep": "requests",
        "path": "app.py",
        "symbol": "sca_requests_vulnerable_call",
    },
}


def _get_lang_config() -> dict[str, str]:
    """Return per-language SCA reachability config, or empty dict if not configured."""
    return _LANG_CONFIG.get(context.library.name, {})


def _cve_id() -> str:
    val = _get_lang_config().get("cve_id")
    assert val is not None, f"No cve_id configured for '{context.library.name}'. Add entry to _LANG_CONFIG."
    return val


def _vulnerable_dep() -> str:
    val = _get_lang_config().get("vulnerable_dep")
    assert val is not None, f"No vulnerable_dep configured for '{context.library.name}'. Add entry to _LANG_CONFIG."
    return val


def _expected_path() -> str | None:
    """Return expected caller path, or None if not yet configured for this language."""
    return _get_lang_config().get("path")


def _expected_symbol() -> str | None:
    """Return expected caller symbol (symbol), or None if not yet configured for this language."""
    return _get_lang_config().get("symbol")


def get_request_content(data: dict[str, Any]) -> dict[str, Any]:
    return data["request"]["content"]


def get_request_type(data: dict[str, Any]) -> str | None:
    return get_request_content(data).get("request_type")


def _get_dependency_cve_metadata(dep_name: str, cve_id: str) -> list[dict[str, Any]]:
    """Collect all reachability metadata entries for a dep+CVE across all telemetry events."""
    results: list[dict[str, Any]] = []
    for data in interfaces.library.get_telemetry_data():
        if get_request_type(data) != "app-dependencies-loaded":
            continue
        for dep in get_request_content(data)["payload"]["dependencies"]:
            if dep.get("name") != dep_name or "metadata" not in dep:
                continue
            for meta in dep["metadata"]:
                if meta.get("type") != "reachability":
                    continue
                value = json.loads(meta["value"])
                if value.get("id") == cve_id:
                    results.append(value)
    return results


def _get_deps_with_reachability_metadata() -> set[str]:
    """Return set of dependency names that have reachability metadata in telemetry."""
    deps: set[str] = set()
    for data in interfaces.library.get_telemetry_data():
        if get_request_type(data) != "app-dependencies-loaded":
            continue
        for dep in get_request_content(data)["payload"]["dependencies"]:
            if "metadata" not in dep:
                continue
            for meta in dep["metadata"]:
                if meta.get("type") == "reachability":
                    deps.add(dep["name"])
                    break
    return deps


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_Dependencies_Have_Metadata:
    """When DD_APPSEC_SCA_ENABLED=true, vulnerable dependencies have reachability metadata."""

    def setup_dependencies_have_metadata_key(self) -> None:
        self.r = weblog.get("/")

    def test_dependencies_have_metadata_key(self) -> None:
        deps_with_metadata = _get_deps_with_reachability_metadata()
        assert _vulnerable_dep() in deps_with_metadata, (
            f"Expected '{_vulnerable_dep()}' to have reachability metadata. "
            f"Dependencies with metadata: {deps_with_metadata}"
        )


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_CVE_Registered_At_Load_Time:
    """CVEs are registered at startup with reached=[] before any vulnerable call."""

    def setup_cve_registered_at_load_time(self) -> None:
        self.r = weblog.get("/")

    def test_cve_registered_at_load_time(self) -> None:
        cve_entries = _get_dependency_cve_metadata(_vulnerable_dep(), _cve_id())
        assert len(cve_entries) >= 1, f"{_cve_id()} not found in {_vulnerable_dep()} dependency metadata at load time"
        # At least one event should have reached=[] (the initial registration before any call)
        empty_reached = [e for e in cve_entries if e["reached"] == []]
        assert len(empty_reached) >= 1, (
            f"Expected at least one {_cve_id()} entry with reached=[] (load-time registration). Got: {cve_entries}"
        )


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_CVE_After_Vulnerable_Call:
    """Calling a vulnerable function reports CVE with caller info in reached array."""

    def setup_cve_metadata_after_vulnerable_call(self) -> None:
        self.r0 = weblog.get("/")
        self.r1 = weblog.get("/sca/vulnerable-call")

    def test_cve_metadata_after_vulnerable_call(self) -> None:
        cve_entries = _get_dependency_cve_metadata(_vulnerable_dep(), _cve_id())
        assert len(cve_entries) >= 1, f"{_cve_id()} not found in {_vulnerable_dep()} metadata"

        # Find an entry with a non-empty reached array (after the vulnerable call)
        reached_entries = [e for e in cve_entries if len(e.get("reached", [])) > 0]
        assert len(reached_entries) >= 1, (
            f"Expected at least one {_cve_id()} entry with non-empty reached array. Got: {cve_entries}"
        )

        entry = reached_entries[0]
        assert len(entry["reached"]) == 1, (
            f"Expected exactly 1 reached entry, got {len(entry['reached'])}: {entry['reached']}"
        )

        caller = entry["reached"][0]
        assert "path" in caller, f"Expected 'path' in caller info, got: {caller}"
        assert "symbol" in caller, f"Expected 'symbol' in caller info, got: {caller}"

        expected_path = _expected_path()
        if expected_path is not None:
            assert caller["path"] == expected_path, f"Expected path '{expected_path}', got '{caller['path']}'"

        expected_symbol = _expected_symbol()
        if expected_symbol is not None:
            assert caller["symbol"] == expected_symbol, f"Expected symbol '{expected_symbol}', got '{caller['symbol']}'"


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_First_Hit_Wins:
    """Two call sites for same CVE: only first hit is reported (max 1 reached per entry)."""

    def setup_same_cve_first_hit_wins(self) -> None:
        self.r0 = weblog.get("/")
        self.r1 = weblog.get("/sca/vulnerable-call")
        self.r2 = weblog.get("/sca/vulnerable-call-alt")

    def test_same_cve_first_hit_wins(self) -> None:
        cve_entries = _get_dependency_cve_metadata(_vulnerable_dep(), _cve_id())
        assert len(cve_entries) >= 1, f"{_cve_id()} not found in {_vulnerable_dep()} metadata"

        expected_path = _expected_path()
        expected_symbol = _expected_symbol()

        reached_entries = [e for e in cve_entries if len(e.get("reached", [])) > 0]
        assert len(reached_entries) >= 1, (
            f"Expected at least one {_cve_id()} entry with non-empty reached array after vulnerable calls. "
            f"Got: {cve_entries}"
        )

        for entry in cve_entries:
            assert isinstance(entry["reached"], list)
            assert len(entry["reached"]) <= 1, (
                f"Expected max 1 reached entry per CVE (first hit wins), "
                f"got {len(entry['reached'])}: {entry['reached']}"
            )

            # First-hit-wins: the recorded caller must match the FIRST call site
            # (/sca/vulnerable-call), never be overwritten by the second
            # call site (/sca/vulnerable-call-alt).
            if len(entry["reached"]) == 1:
                caller = entry["reached"][0]
                if expected_path is not None:
                    assert caller.get("path") == expected_path, (
                        f"First-hit-wins violated: expected path '{expected_path}' "
                        f"(first call site), got '{caller.get('path')}'"
                    )
                if expected_symbol is not None:
                    assert caller.get("symbol") == expected_symbol, (
                        f"First-hit-wins violated: expected symbol '{expected_symbol}' "
                        f"(first call site), got '{caller.get('symbol')}'"
                    )


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_Deduplication:
    """Repeated calls from same site for same CVE: still max 1 reached entry."""

    def setup_deduplication_repeated_calls(self) -> None:
        self.r0 = weblog.get("/")
        for _ in range(5):
            weblog.get("/sca/vulnerable-call")

    def test_deduplication_repeated_calls(self) -> None:
        cve_entries = _get_dependency_cve_metadata(_vulnerable_dep(), _cve_id())
        assert len(cve_entries) >= 1, f"{_cve_id()} not found in {_vulnerable_dep()} metadata"

        for entry in cve_entries:
            assert len(entry.get("reached", [])) <= 1, (
                f"Expected max 1 reached entry after 5 calls from same site, "
                f"got {len(entry['reached'])}: {entry['reached']}"
            )
