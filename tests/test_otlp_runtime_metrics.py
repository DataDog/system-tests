"""Test that runtime metrics are exported via OTLP using OTel semantic convention names.

When DD_RUNTIME_METRICS_ENABLED=true and DD_METRICS_OTEL_ENABLED=true, dd-trace-*
libraries should send runtime metrics via OTLP with OTel-native naming (dotnet.*,
jvm.*, go.*, v8js.*, etc.) instead of DD-proprietary naming (runtime.dotnet.*,
runtime.go.*, runtime.node.*, etc.).
"""

from utils import context, features, interfaces, scenarios, weblog


# All OTel semconv metric names that MUST be present per language.
# These are the complete instrument sets from each tracer's OTLP runtime metrics implementation.
EXPECTED_METRICS = {
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
DD_PROPRIETARY_PREFIXES = {
    "dotnet": "runtime.dotnet.",
    "golang": "runtime.go.",
    "nodejs": "runtime.node.",
    "java": "jvm.heap_memory",
}


def get_runtime_metric_names():
    """Extract runtime metric names from the agent interface (agent -> backend series).

    Uses interfaces.agent.get_metrics() — the same approach as
    Test_Config_RuntimeMetrics_Enabled in test_config_consistency.py.
    """
    metric_names = set()
    for _, metric in interfaces.agent.get_metrics():
        metric_names.add(metric["metric"])
    return metric_names


@scenarios.otlp_runtime_metrics
@features.runtime_metrics
class Test_OtlpRuntimeMetrics:
    """Verify runtime metrics are sent via OTLP with OTel names, not DD-proprietary names."""

    def setup_main(self):
        self.req = weblog.get("/")

    def test_main(self):
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
