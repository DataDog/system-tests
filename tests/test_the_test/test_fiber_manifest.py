import pytest

from utils import features, scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest, SkipDeclaration


DEBUGGER_NODEIDS = [
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Line_Probe_Snaphots::test_log_line_snapshot",
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Line_Probe_Snaphots_With_SCM::test_log_line_snapshot",
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Method_Probe_Snaphots::test_log_method_snapshot",
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Method_Probe_Snaphots_With_SCM::test_log_method_snapshot",
    "tests/debugger/test_debugger_probe_status.py::Test_Debugger_Method_Probe_Statuses::test_log_method_status",
]


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize(
    ("agent_version", "has_bug"),
    [
        ("7.78.0", False),
        ("7.79.0-dev", False),
        ("7.79.0-devel", True),
        ("7.79.0-rc.1", True),
        ("7.79.0", True),
        ("7.83.2", True),
    ],
)
def test_fiber_debugger_bug_is_version_scoped(agent_version: str, *, has_bug: bool) -> None:
    manifest = Manifest({"golang": Version("2.12.0-dev"), "agent": Version(agent_version)}, "fiber-v2-orchestrion")
    expected = [SkipDeclaration("bug", "DEBUG-5421")] if has_bug else []
    for nodeid in DEBUGGER_NODEIDS:
        assert manifest.get_declarations(nodeid) == expected, nodeid

    # Do not disable the whole class or add the Agent bug to unrelated probe types.
    assert (
        manifest.get_declarations("tests/debugger/test_debugger_probe_status.py::Test_Debugger_Method_Probe_Statuses")
        == []
    )
    assert manifest.get_declarations(
        "tests/debugger/test_debugger_probe_status.py::Test_Debugger_Method_Probe_Statuses::test_metric_status"
    ) == [SkipDeclaration("missing_feature", "Not yet implemented")]


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("weblog", ["fiber-v2-orchestrion", "net-http-orchestrion", "gin"])
@pytest.mark.parametrize(
    "test_name", ["test_new_traceid", "test_incoming_64bit_traceid", "test_incoming_128bit_traceid"]
)
def test_fiber_inherits_only_the_automatic_log_injection_bug(weblog: str, test_name: str) -> None:
    manifest = Manifest({"golang": Version("2.12.0-dev")}, weblog)
    expected = [] if weblog == "gin" else [SkipDeclaration("bug", "APMLP-659")]
    assert (
        manifest.get_declarations(
            f"tests/test_config_consistency.py::Test_Config_LogInjection_128Bit_TraceId_Disabled::{test_name}"
        )
        == expected
    )


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("library_version", ["1.72.0", "1.73.0-dev", "2.10.1", "2.12.0-dev.3"])
@pytest.mark.parametrize("weblog", ["fiber-v2-orchestrion", "net-http-orchestrion", "gin"])
def test_fiber_standalone_requires_http_appsec_support(library_version: str, weblog: str) -> None:
    manifest = Manifest({"golang": Version(library_version)}, weblog)
    if weblog == "fiber-v2-orchestrion":
        expected = [SkipDeclaration("missing_feature", "Fiber HTTP AppSec support is not released")]
    elif Version(library_version) < Version("1.73.0-dev"):
        expected = [SkipDeclaration("missing_feature", "declared version for golang is v1.73.0-dev")]
    else:
        expected = []
    nodeid = "tests/appsec/test_asm_standalone.py::Test_AppSecStandalone_UpstreamPropagation_V2"
    assert manifest.get_declarations(nodeid) == expected
    assert (
        manifest.get_declarations(f"{nodeid}::test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_0")
        == expected
    )


@features.not_reported
@scenarios.test_the_test
def test_fiber_otlp_remains_enabled() -> None:
    manifest = Manifest({"golang": Version("2.12.0-dev"), "agent": Version("7.83.2")}, "fiber-v2-orchestrion")
    for nodeid in (
        "Test_Otel_Tracing_OTLP::test_single_server_trace",
        "Test_Otel_Tracing_OTLP::test_unsampled_trace",
        "Test_Otel_Tracing_OTLP::test_128bit_trace_id_consistent_across_spans",
        "Test_Otlp_Carries_Ot::test_otlp_carries_ot",
        "Test_Otlp_Forwards_Inherited_Ot::test_otlp_forwards_inherited_ot",
    ):
        assert manifest.get_declarations(f"tests/otel/test_tracing_otlp.py::{nodeid}") == []
