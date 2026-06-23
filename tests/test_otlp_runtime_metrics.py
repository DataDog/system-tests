"""Test that runtime metrics are exported via OTLP using OTel semantic convention names.

When DD_RUNTIME_METRICS_ENABLED=true and DD_METRICS_OTEL_ENABLED=true, dd-trace-*
libraries should send runtime metrics via OTLP with OTel-native naming (dotnet.*,
jvm.*, go.*, v8js.*, etc.) instead of DD-proprietary naming (runtime.dotnet.*,
runtime.go.*, runtime.node.*, etc.).
"""

from typing import TypedDict

from utils import context, features, interfaces, scenarios, weblog


class MetricConstraints(TypedDict, total=False):
    """Attribute constraints for an expected metric.

    all: keys required on every data point.
    some: keys required on at least one data point.
    present_values: attribute -> values that must each appear on at least one data point.
    """

    all: list[str]
    some: list[str]
    present_values: dict[str, list[str]]


# Maps each expected metric to its attribute constraints (see MetricConstraints).
EXPECTED_METRICS: dict[str, dict[str, MetricConstraints]] = {
    "dotnet": {
        "dotnet.assembly.count": {"all": []},
        "dotnet.exceptions": {"all": []},
        "dotnet.gc.collections": {"all": []},
        "dotnet.gc.heap.total_allocated": {"all": []},
        "dotnet.gc.last_collection.heap.fragmentation.size": {"all": []},
        "dotnet.gc.last_collection.heap.size": {"all": []},
        "dotnet.gc.last_collection.memory.committed_size": {"all": []},
        "dotnet.gc.pause.time": {"all": []},
        "dotnet.jit.compilation.time": {"all": []},
        "dotnet.jit.compiled_il.size": {"all": []},
        "dotnet.jit.compiled_methods": {"all": []},
        "dotnet.monitor.lock_contentions": {"all": []},
        "dotnet.process.cpu.count": {"all": []},
        "dotnet.process.cpu.time": {"all": []},
        "dotnet.process.memory.working_set": {"all": []},
        "dotnet.thread_pool.queue.length": {"all": []},
        "dotnet.thread_pool.thread.count": {"all": []},
        "dotnet.thread_pool.work_item.count": {"all": []},
        "dotnet.timer.count": {"all": []},
    },
    "golang": {
        "go.config.gogc": {"all": []},
        "go.goroutine.count": {"all": []},
        "go.memory.allocated": {"all": []},
        "go.memory.allocations": {"all": []},
        "go.memory.gc.goal": {"all": []},
        "go.memory.limit": {"all": []},
        "go.memory.used": {"all": []},
        "go.processor.limit": {"all": []},
    },
    "nodejs": {
        "nodejs.eventloop.delay.max": {"all": []},
        "nodejs.eventloop.delay.mean": {"all": []},
        "nodejs.eventloop.delay.min": {"all": []},
        "nodejs.eventloop.delay.p50": {"all": []},
        "nodejs.eventloop.delay.p90": {"all": []},
        "nodejs.eventloop.delay.p99": {"all": []},
        "nodejs.eventloop.delay.stddev": {"all": []},
        "nodejs.eventloop.time": {"all": ["nodejs.eventloop.state"]},
        "nodejs.eventloop.utilization": {"all": []},
        # v8js.gc.duration is a histogram; the agent surfaces it as .count/.sum/.min/.max series.
        "v8js.gc.duration.count": {"all": ["v8js.gc.type"]},
        "v8js.gc.duration.max": {"all": ["v8js.gc.type"]},
        "v8js.gc.duration.min": {"all": ["v8js.gc.type"]},
        "v8js.gc.duration.sum": {"all": ["v8js.gc.type"]},
        # v8js.memory.heap.limit emits a single aggregate point (heap_size_limit) without a space tag;
        # all other heap instruments emit per-space points carrying v8js.heap.space.name.
        "v8js.memory.heap.limit": {"all": []},
        "v8js.memory.heap.space.available_size": {"all": ["v8js.heap.space.name"]},
        "v8js.memory.heap.space.physical_size": {"all": ["v8js.heap.space.name"]},
        "v8js.memory.heap.space.size": {"all": ["v8js.heap.space.name"]},
        "v8js.memory.heap.used": {"all": ["v8js.heap.space.name"]},
        # v8js.resource.type is open-ended, so assert a known value is present instead of using a
        # closed allow-list: the weblog's listening HTTP server always emits TCPServerWrap.
        "v8js.resource.active": {
            "all": ["v8js.resource.type"],
            "present_values": {"v8js.resource.type": ["TCPServerWrap"]},
        },
    },
    "java": {
        "jvm.buffer.count": {"all": ["jvm.buffer.pool.name"]},
        "jvm.buffer.memory.limit": {"all": ["jvm.buffer.pool.name"]},
        "jvm.buffer.memory.used": {"all": ["jvm.buffer.pool.name"]},
        "jvm.class.count": {"all": []},
        "jvm.class.loaded": {"all": []},
        "jvm.class.unloaded": {"all": []},
        "jvm.cpu.count": {"all": []},
        "jvm.cpu.recent_utilization": {"all": []},
        "jvm.cpu.time": {"all": []},
        # jvm.gc.duration is a histogram; the agent surfaces it as .count/.sum/.min/.max series.
        "jvm.gc.duration.count": {"all": ["jvm.gc.name", "jvm.gc.action", "jvm.gc.cause"]},
        "jvm.gc.duration.sum": {"all": ["jvm.gc.name", "jvm.gc.action", "jvm.gc.cause"]},
        "jvm.gc.duration.min": {"all": ["jvm.gc.name", "jvm.gc.action", "jvm.gc.cause"]},
        "jvm.gc.duration.max": {"all": ["jvm.gc.name", "jvm.gc.action", "jvm.gc.cause"]},
        # memory metrics emit per-pool points (with pool.name) and aggregate totals (without),
        # so jvm.memory.type is required on all points and pool.name on at least one.
        "jvm.memory.committed": {"all": ["jvm.memory.type"], "some": ["jvm.memory.pool.name"]},
        "jvm.memory.init": {"all": ["jvm.memory.type"], "some": ["jvm.memory.pool.name"]},
        "jvm.memory.limit": {"all": ["jvm.memory.type"], "some": ["jvm.memory.pool.name"]},
        "jvm.memory.used": {"all": ["jvm.memory.type"], "some": ["jvm.memory.pool.name"]},
        # used_after_last_gc only emits per-pool points — both attributes are always present.
        "jvm.memory.used_after_last_gc": {"all": ["jvm.memory.pool.name", "jvm.memory.type"]},
        "jvm.thread.count": {"all": ["jvm.thread.daemon", "jvm.thread.state"]},
        # experimental metrics (on by default); no domain-specific attributes.
        "jvm.system.cpu.utilization": {"all": []},
        "jvm.system.cpu.load_1m": {"all": []},
        "jvm.file_descriptor.count": {"all": []},
        "jvm.file_descriptor.limit": {"all": []},
    },
}

# Valid value domains for attributes. For closed enums (jvm.memory.type, jvm.thread.*,
# nodejs.eventloop.state, v8js.gc.type) these are exhaustive. For open-ended attributes
# (pool names, GC names, V8 heap space names) these are supersets covering all known
# implementations — the assertion is that observed values fall within the known universe.
EXPECTED_METRIC_ATTRIBUTE_VALUES: dict[str, dict[str, frozenset[str]]] = {
    "nodejs": {
        # Closed enum: performance.eventLoopUtilization() exposes idle and active only.
        "nodejs.eventloop.state": frozenset({"active", "idle"}),
        # Closed enum: dd-trace-js maps perf_hooks GC kinds to these four OTel values.
        # Kind 2 (V8 MinorMarkSweep on Node 20+) is mapped to "minor" upstream.
        "v8js.gc.type": frozenset({"minor", "major", "incremental", "weakcb"}),
        # V8 heap space names: OTel well-known set plus additional spaces V8 exposes in
        # Node 18+ (read_only, *_large_object) and Node 20+ multi-isolate/sandbox spaces.
        "v8js.heap.space.name": frozenset(
            {
                "new_space",
                "old_space",
                "code_space",
                "large_object_space",
                "map_space",
                "read_only_space",
                "new_large_object_space",
                "code_large_object_space",
                "shared_space",
                "shared_large_object_space",
                "trusted_space",
                "trusted_large_object_space",
                "shared_trusted_space",
                "shared_trusted_large_object_space",
            }
        ),
        # v8js.resource.type is open-ended (validated via present_values in EXPECTED_METRICS, not here).
    },
    "java": {
        "jvm.memory.type": frozenset({"heap", "non_heap"}),
        "jvm.thread.daemon": frozenset({"true", "false"}),
        "jvm.thread.state": frozenset({"new", "runnable", "blocked", "waiting", "timed_waiting", "terminated"}),
        # Pool names vary by GC algorithm; superset across G1GC, ZGC, Shenandoah, ParallelGC, SerialGC, CMS.
        # Values are emitted as raw JMX strings (mixed case, spaces, quotes preserved).
        "jvm.memory.pool.name": frozenset(
            {
                # G1GC
                "G1 Eden Space",
                "G1 Survivor Space",
                "G1 Old Gen",
                # ZGC
                "ZHeap",
                # Shenandoah
                "Shenandoah",
                # ParallelGC
                "PS Eden Space",
                "PS Survivor Space",
                "PS Old Gen",
                # SerialGC / CMS young
                "Eden Space",
                "Survivor Space",
                # SerialGC old
                "Tenured Gen",
                # CMS
                "Par Eden Space",
                "Par Survivor Space",
                "CMS Old Gen",
                # Non-heap regions common across all GCs
                "Metaspace",
                "Compressed Class Space",
                # Code Cache (monolithic, JDK < 9 or -XX:-SegmentedCodeCache)
                "Code Cache",
                # Segmented Code Cache (JDK 9+)
                "CodeHeap 'non-nmethods'",
                "CodeHeap 'profiled nmethods'",
                "CodeHeap 'non-profiled nmethods'",
            }
        ),
        # Buffer pool names are stable across JVM versions.
        "jvm.buffer.pool.name": frozenset(
            {
                "direct",
                "mapped",
                "mapped - 'non-volatile memory'",  # JDK 14+ non-volatile MappedByteBuffer
            }
        ),
        # GC collector names vary by algorithm.
        "jvm.gc.name": frozenset(
            {
                # G1GC
                "G1 Young Generation",
                "G1 Old Generation",
                "G1 Concurrent GC",
                # ZGC
                "ZGC",
                "ZGC Pauses",
                "ZGC Cycles",
                # Shenandoah
                "Shenandoah Cycles",
                "Shenandoah Pauses",
                # ParallelGC
                "PS Scavenge",
                "PS MarkSweep",
                # SerialGC
                "Copy",
                "MarkSweepCompact",
                # CMS (deprecated but still encountered)
                "ParNew",
                "ConcurrentMarkSweep",
            }
        ),
        "jvm.gc.action": frozenset({"end of minor GC", "end of major GC", "end of GC cycle"}),
    },
}

# DD-proprietary prefixes that should NOT appear when OTLP metrics are active.
DD_PROPRIETARY_PREFIXES: dict[str, str] = {
    "dotnet": "runtime.dotnet.",
    "golang": "runtime.go.",
    "nodejs": "runtime.node.",
    "java": "jvm.heap_memory",
}


def get_runtime_metrics_by_name() -> dict[str, list[dict[str, str]]]:
    """Return observed runtime metrics grouped by name.

    Each entry maps metric name -> list of tag dicts, one per data point.
    Tags are parsed from "key:value" strings in the agent series.
    """
    result: dict[str, list[dict[str, str]]] = {}
    for _, metric in interfaces.agent.get_metrics():
        name: str = metric["metric"]
        tags: dict[str, str] = dict(tag.split(":", 1) for tag in metric.get("tags", []) if ":" in tag)
        result.setdefault(name, []).append(tags)
    return result


@scenarios.otlp_runtime_metrics
@features.runtime_metrics
class Test_OtlpRuntimeMetrics:
    """Verify runtime metrics are sent via OTLP with OTel names, not DD-proprietary names."""

    def setup_otel_metrics_are_present_and_attributed(self) -> None:
        self.req = weblog.get("/")

    def test_otel_metrics_are_present_and_attributed(self) -> None:
        assert self.req.status_code == 200

        library = context.library.name
        if library not in EXPECTED_METRICS:
            return

        observed = get_runtime_metrics_by_name()
        attribute_values = EXPECTED_METRIC_ATTRIBUTE_VALUES.get(library, {})

        for metric_name, constraints in EXPECTED_METRICS[library].items():
            assert metric_name in observed, (
                f"Expected OTel runtime metric '{metric_name}' not found for {library}. "
                f"Got metrics: {sorted(observed.keys())}"
            )

            points = observed[metric_name]
            all_keys = constraints.get("all", [])
            some_keys = constraints.get("some", [])

            for point_tags in points:
                for key in all_keys:
                    assert key in point_tags, (
                        f"Metric '{metric_name}' data point missing required attribute '{key}' "
                        f"for {library}. Got tags: {point_tags}"
                    )
                    if key in attribute_values:
                        assert point_tags[key] in attribute_values[key], (
                            f"Metric '{metric_name}' attribute '{key}' has invalid value "
                            f"'{point_tags[key]}' for {library}. "
                            f"Expected one of: {sorted(attribute_values[key])}"
                        )

            for key in some_keys:
                assert any(key in point_tags for point_tags in points), (
                    f"Metric '{metric_name}' has no data point with attribute '{key}' for {library}."
                )
                for point_tags in points:
                    if key in point_tags and key in attribute_values:
                        assert point_tags[key] in attribute_values[key], (
                            f"Metric '{metric_name}' attribute '{key}' has invalid value "
                            f"'{point_tags[key]}' for {library}. "
                            f"Expected one of: {sorted(attribute_values[key])}"
                        )

            for attr_key, required_values in constraints.get("present_values", {}).items():
                observed_values = {pt[attr_key] for pt in points if attr_key in pt}
                for required_value in required_values:
                    assert required_value in observed_values, (
                        f"Metric '{metric_name}' expected at least one data point with "
                        f"{attr_key}='{required_value}' for {library}. "
                        f"Observed {attr_key} values: {sorted(observed_values)}"
                    )

    def setup_dd_metrics_are_absent(self) -> None:
        self.req = weblog.get("/")

    def test_dd_metrics_are_absent(self) -> None:
        assert self.req.status_code == 200

        library = context.library.name
        dd_prefix = DD_PROPRIETARY_PREFIXES.get(library)
        if not dd_prefix:
            return

        observed = get_runtime_metrics_by_name()
        dd_named_metrics = [n for n in observed if n.startswith(dd_prefix)]
        assert len(dd_named_metrics) == 0, (
            f"Found DD-proprietary metric names for {library}: {dd_named_metrics}. Expected OTel-native names only."
        )
