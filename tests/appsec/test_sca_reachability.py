"""Tests for SCA Runtime Reachability feature.

When DD_APPSEC_SCA_ENABLED=true, the tracer reports CVE metadata on vulnerable
dependencies via telemetry app-dependencies-loaded events. When a vulnerable
function is called, caller information is added to the reached array.

RFC: https://docs.google.com/document/d/1xDw9iG6h41VCEgJGTqoJdruRaNS4pYgNifO6nhiizWA/edit
"""

import json
from typing import Any

from utils import weblog, interfaces, scenarios, features, rfc

SCA_REACHABILITY_RFC = "https://docs.google.com/document/d/1xDw9iG6h41VCEgJGTqoJdruRaNS4pYgNifO6nhiizWA/edit"

CVE_ID = "CVE-2024-35195"
VULNERABLE_DEP = "requests"


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
        assert VULNERABLE_DEP in deps_with_metadata, (
            f"Expected '{VULNERABLE_DEP}' to have reachability metadata. "
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
        cve_entries = _get_dependency_cve_metadata(VULNERABLE_DEP, CVE_ID)
        assert len(cve_entries) >= 1, f"{CVE_ID} not found in {VULNERABLE_DEP} dependency metadata at load time"
        # At least one event should have reached=[] (the initial registration before any call)
        empty_reached = [e for e in cve_entries if e["reached"] == []]
        assert len(empty_reached) >= 1, (
            f"Expected at least one {CVE_ID} entry with reached=[] (load-time registration). Got: {cve_entries}"
        )


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_CVE_After_Vulnerable_Call:
    """Calling a vulnerable function reports CVE with caller info in reached array."""

    def setup_cve_metadata_after_vulnerable_call(self) -> None:
        self.r0 = weblog.get("/")
        self.r1 = weblog.get("/sca/requests/vulnerable-call")

    def test_cve_metadata_after_vulnerable_call(self) -> None:
        cve_entries = _get_dependency_cve_metadata(VULNERABLE_DEP, CVE_ID)
        assert len(cve_entries) >= 1, f"{CVE_ID} not found in {VULNERABLE_DEP} metadata"

        # Find an entry with a non-empty reached array (after the vulnerable call)
        reached_entries = [e for e in cve_entries if len(e.get("reached", [])) > 0]
        assert len(reached_entries) >= 1, (
            f"Expected at least one {CVE_ID} entry with non-empty reached array. Got: {cve_entries}"
        )

        caller = reached_entries[0]["reached"][0]
        assert "path" in caller, f"Expected 'path' in caller info, got: {caller}"
        assert "method" in caller, f"Expected 'method' in caller info, got: {caller}"
        assert "line" in caller, f"Expected 'line' in caller info, got: {caller}"
        assert caller.get("line", 0) > 0, f"Expected non-zero line number, got: {caller}"


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_First_Hit_Wins:
    """Two call sites for same CVE: only first hit is reported (max 1 reached per entry)."""

    def setup_same_cve_first_hit_wins(self) -> None:
        self.r0 = weblog.get("/")
        self.r1 = weblog.get("/sca/requests/vulnerable-call")
        self.r2 = weblog.get("/sca/requests/vulnerable-call-alt")

    def test_same_cve_first_hit_wins(self) -> None:
        cve_entries = _get_dependency_cve_metadata(VULNERABLE_DEP, CVE_ID)
        assert len(cve_entries) >= 1, f"{CVE_ID} not found in {VULNERABLE_DEP} metadata"

        for entry in cve_entries:
            assert isinstance(entry["reached"], list)
            assert len(entry["reached"]) <= 1, (
                f"Expected max 1 reached entry per CVE (first hit wins), "
                f"got {len(entry['reached'])}: {entry['reached']}"
            )


@rfc(SCA_REACHABILITY_RFC)
@features.runtime_sca_reachability
@scenarios.runtime_sca_reachability
class Test_SCA_Reachability_Deduplication:
    """Repeated calls from same site for same CVE: still max 1 reached entry."""

    def setup_deduplication_repeated_calls(self) -> None:
        self.r0 = weblog.get("/")
        for _ in range(5):
            weblog.get("/sca/requests/vulnerable-call")

    def test_deduplication_repeated_calls(self) -> None:
        cve_entries = _get_dependency_cve_metadata(VULNERABLE_DEP, CVE_ID)
        assert len(cve_entries) >= 1, f"{CVE_ID} not found in {VULNERABLE_DEP} metadata"

        for entry in cve_entries:
            assert len(entry.get("reached", [])) <= 1, (
                f"Expected max 1 reached entry after 5 calls from same site, "
                f"got {len(entry['reached'])}: {entry['reached']}"
            )
