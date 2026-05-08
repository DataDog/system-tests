"""Test that runtime metrics are exported via OTLP using OTel semantic convention names.

When DD_RUNTIME_METRICS_ENABLED=true and DD_METRICS_OTEL_ENABLED=true, dd-trace-*
libraries should send runtime metrics via OTLP with OTel-native naming (dotnet.*,
jvm.*, go.*, v8js.*, etc.) instead of DD-proprietary naming (runtime.dotnet.*,
runtime.go.*, runtime.node.*, etc.).
"""

from __future__ import annotations

from typing import Any

from utils import context, features, interfaces, scenarios, weblog


# All OTel semconv metric names that MUST be present per language.
# These are the complete instrument sets from each tracer's OTLP runtime metrics implementation.
EXPECTED_METRICS: dict[str, list[str]] = {
    "dotnet": [
        "dotnet.assembly.count",
        "dotnet.exceptions",
        "dotnet.gc.collections",
        "dotnet.gc.heap.total_allocated",
        "dotnet.gc.last_collection.heap.fragmentation.size",
        "dotnet.gc.last_collection.heap.size",
        "dotnet.gc.last_collection.memory.committed_size",
        "dotnet.gc.pause.time",
        "dotnet.jit.compilation.time",
        "dotnet.jit.compiled_il.size",
        "dotnet.jit.compiled_methods",
        "dotnet.monitor.lock_contentions",
        "dotnet.process.cpu.count",
        "dotnet.process.cpu.time",
        "dotnet.process.memory.working_set",
        "dotnet.thread_pool.queue.length",
        "dotnet.thread_pool.thread.count",
        "dotnet.thread_pool.work_item.count",
        "dotnet.timer.count",
    ],
    "golang": [
        "go.config.gogc",
        "go.goroutine.count",
        "go.memory.allocated",
        "go.memory.allocations",
        "go.memory.gc.goal",
        "go.memory.limit",
        "go.memory.used",
        "go.processor.limit",
    ],
    "nodejs": [
        "nodejs.eventloop.delay.max",
        "nodejs.eventloop.delay.mean",
        "nodejs.eventloop.delay.min",
        "nodejs.eventloop.delay.p50",
        "nodejs.eventloop.delay.p90",
        "nodejs.eventloop.delay.p99",
        "nodejs.eventloop.utilization",
        "process.cpu.utilization",
        "process.memory.usage",
        "v8js.memory.heap.limit",
        "v8js.memory.heap.space.available_size",
        "v8js.memory.heap.space.physical_size",
        "v8js.memory.heap.used",
    ],
    "java": [
        "jvm.buffer.count",
        "jvm.buffer.memory.limit",
        "jvm.buffer.memory.used",
        "jvm.class.count",
        "jvm.class.loaded",
        "jvm.class.unloaded",
        "jvm.cpu.count",
        "jvm.cpu.recent_utilization",
        "jvm.cpu.time",
        "jvm.file_descriptor.count",
        "jvm.file_descriptor.limit",
        "jvm.memory.committed",
        "jvm.memory.init",
        "jvm.memory.limit",
        "jvm.memory.used",
        "jvm.memory.used_after_last_gc",
        "jvm.system.cpu.utilization",
        "jvm.thread.count",
    ],
}

# DD-proprietary prefixes that should NOT appear when OTLP metrics are active
DD_PROPRIETARY_PREFIXES: dict[str, str] = {
    "dotnet": "runtime.dotnet.",
    "golang": "runtime.go.",
    "nodejs": "runtime.node.",
    "java": "jvm.heap_memory",
}

# Extended Go metrics emitted when DD_OTEL_RUNTIME_METRICS_EXTENDED_ENABLED=true
EXPECTED_METRICS_GOLANG_EXTENDED: list[str] = [
    "go.cpu.time",
    "go.memory.gc.cycles",
]

# Expected attribute values for Go metric dimensions
_GOLANG_MEMORY_USED_TYPES: set[str] = {"other", "stack"}
_GOLANG_CPU_TIME_STATES: set[str] = {"gc_mark_assist", "gc_dedicated", "gc_pauses", "idle", "user"}
_GOLANG_GC_CYCLES_TYPES: set[str] = {"automatic", "forced"}

# OTel instrumentation scope name used by the Go runtime metrics collector
_GO_RUNTIME_SCOPE = "go.runtime"


def get_runtime_metric_names() -> set[str]:
    """Extract runtime metric names from the agent interface (agent -> backend series)."""
    metric_names: set[str] = set()
    for _, metric in interfaces.agent.get_metrics():
        metric_names.add(metric["metric"])
    return metric_names


def _collect_go_otlp_metrics() -> dict[str, list[dict[str, Any]]]:
    """Collect Go runtime metrics from raw OTLP payloads captured at the proxy.

    Returns metric_name -> list of OTLP data points for scope 'go.runtime'.
    """
    metrics: dict[str, list[dict[str, Any]]] = {}
    for data in interfaces.open_telemetry.get_data(path_filters=["/v1/metrics"]):
        content: dict[str, Any] = data["request"]["content"]
        for resource_metric in content.get("resourceMetrics", []):
            for scope_metric in resource_metric.get("scopeMetrics", []):
                scope_name: str = scope_metric.get("scope", {}).get("name", "")
                if scope_name != _GO_RUNTIME_SCOPE:
                    continue
                for metric in scope_metric.get("metrics", []):
                    name: str = metric["name"]
                    data_points: list[dict[str, Any]] = metric.get("sum", {}).get("dataPoints", []) or metric.get(
                        "gauge", {}
                    ).get("dataPoints", [])
                    if name not in metrics:
                        metrics[name] = []
                    metrics[name].extend(data_points)
    return metrics


def _get_attribute_values(data_points: list[dict[str, Any]], attr_key: str) -> set[str]:
    """Extract all string values for a given attribute key from OTel data points."""
    values: set[str] = set()
    for dp in data_points:
        for attr in dp.get("attributes", []):
            if attr["key"] == attr_key:
                values.add(attr.get("value", {}).get("stringValue", ""))
    return values


@scenarios.otlp_runtime_metrics
@features.runtime_metrics
class Test_OtlpRuntimeMetrics:
    """Verify runtime metrics are sent via OTLP with OTel names, not DD-proprietary names.

    For Go: also validates metrics appear in the raw OTLP payload from the correct
    instrumentation scope, and that go.memory.used carries both memory-type dimensions.
    """

    def setup_main(self) -> None:
        self.req = weblog.get("/")

    def test_main(self) -> None:
        assert self.req.status_code == 200

        library = context.library.name
        if library not in EXPECTED_METRICS:
            return

        metric_names = get_runtime_metric_names()

        # All expected OTel-named metrics must be present
        expected = EXPECTED_METRICS[library]
        for expected_name in expected:
            assert expected_name in metric_names, (
                f"Expected OTel runtime metric '{expected_name}' not found for {library}. "
                f"Got metrics: {sorted(metric_names)}"
            )

        # DD-proprietary names must NOT be present
        dd_prefix = DD_PROPRIETARY_PREFIXES.get(library)
        if dd_prefix:
            dd_named_metrics = [n for n in metric_names if n.startswith(dd_prefix)]
            assert len(dd_named_metrics) == 0, (
                f"Found DD-proprietary metric names for {library}: {dd_named_metrics}. Expected OTel-native names only."
            )

        # For Go: additionally validate the raw OTLP payload (scope + attributes)
        if library == "golang":
            otlp_metrics = _collect_go_otlp_metrics()
            for name in EXPECTED_METRICS["golang"]:
                assert name in otlp_metrics, (
                    f"OTel metric '{name}' not found in OTLP payload from scope '{_GO_RUNTIME_SCOPE}'. "
                    f"Found: {sorted(otlp_metrics.keys())}"
                )
            # go.memory.used must report both heap-object and stack memory dimensions
            memory_used_types = _get_attribute_values(otlp_metrics.get("go.memory.used", []), "go.memory.type")
            assert memory_used_types == _GOLANG_MEMORY_USED_TYPES, (
                f"go.memory.used: expected go.memory.type values {_GOLANG_MEMORY_USED_TYPES}, got {memory_used_types}"
            )


@scenarios.otlp_runtime_metrics_extended
@features.runtime_metrics
class Test_GoOtlpRuntimeMetricsExtended:
    """Validate extended Go runtime metrics when DD_OTEL_RUNTIME_METRICS_EXTENDED_ENABLED=true.

    Extended metrics: go.cpu.time (per CPU state) and go.memory.gc.cycles (per GC type).
    """

    def setup_main(self) -> None:
        self.req = weblog.get("/")

    def test_main(self) -> None:
        if context.library.name != "golang":
            return

        assert self.req.status_code == 200

        metrics = _collect_go_otlp_metrics()

        # Recommended metrics must still be present in the extended scenario
        for name in EXPECTED_METRICS["golang"]:
            assert name in metrics, (
                f"Recommended OTel metric '{name}' missing in extended scenario. Found: {sorted(metrics.keys())}"
            )

        # Extended-only metrics must be present
        for name in EXPECTED_METRICS_GOLANG_EXTENDED:
            assert name in metrics, f"Extended OTel metric '{name}' not found. Found: {sorted(metrics.keys())}"

        # go.cpu.time must carry all expected CPU state dimensions
        cpu_time_states = _get_attribute_values(metrics.get("go.cpu.time", []), "go.cpu.state")
        assert cpu_time_states == _GOLANG_CPU_TIME_STATES, (
            f"go.cpu.time: expected go.cpu.state values {_GOLANG_CPU_TIME_STATES}, got {cpu_time_states}"
        )

        # go.memory.gc.cycles must carry both GC type dimensions
        gc_cycles_types = _get_attribute_values(metrics.get("go.memory.gc.cycles", []), "go.gc.type")
        assert gc_cycles_types == _GOLANG_GC_CYCLES_TYPES, (
            f"go.memory.gc.cycles: expected go.gc.type values {_GOLANG_GC_CYCLES_TYPES}, got {gc_cycles_types}"
        )
