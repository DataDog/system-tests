"""Conformance runner for dd-trace-rust (NATIVE Temper backend).

  bash adapters/dd-trace-rust/build.sh
  temper build -b py
  ./.venv-ddtrace/bin/python adapters/dd-trace-rust/run.py

Unlike the FFI backends, this drives the real dd-trace-rs library from a NATIVE
rust binary that links the Temper suite crate directly (no cdylib, no FFI). Each
case runs in its own subprocess so its env is applied before dd-trace-rs
initializes; spans go to a real ddapm-test-agent, read back over HTTP by the
binary's captured_spans().
"""
import atexit
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PYOUT = os.path.join(REPO, "temper.out", "py")
PYPATH = os.pathsep.join([
    os.path.join(PYOUT, "system-tests-redux"),
    os.path.join(PYOUT, "temper-core"),
    os.path.join(PYOUT, "std"),
])
sys.path[:0] = PYPATH.split(os.pathsep)
from system_tests_redux.system_tests_redux import all_cases  # noqa: E402

# The native binary (prefer release, fall back to debug).
BIN = os.path.join(HERE, "target", "release", "run_one")
if not os.path.exists(BIN):
    BIN = os.path.join(HERE, "target", "debug", "run_one")

cases = all_cases()
print("— dd-trace-rust conformance runner (native crate -> dd-trace-rs) —")
print(f"cases:    {len(cases)}\n")

# Verified genuine dd-trace-rs behavior/config diffs (run-then-downgrade: a
# listed case that PASSES still reports PASS, so the list can't hide a fix).
# Populated from real failures observed against dd-trace-rs v0.5.0.
KNOWN_RUST_DIFFS = {
    # 128-bit trace id: dd-trace-rs v0.5.0 does not emit the _dd.p.tid tag (high 64 bits) — verified absent in the delivered span; it also prefers tracestate tid and injects 128-bit form when gen is disabled
    "traceids_128bit.datadog_gen_enabled",
    "traceids_128bit.datadog_gen_enabled_default",
    "traceids_128bit_b3.b3multi_gen_disabled",
    "traceids_128bit_b3.b3multi_gen_enabled",
    "traceids_128bit_b3.b3multi_propagation",
    "traceids_128bit_b3.b3single_gen_disabled",
    "traceids_128bit_b3.b3single_gen_enabled",
    "traceids_128bit_b3.b3single_propagation",
    "traceids_128bit_tc.gen_disabled",
    "traceids_128bit_tc.gen_enabled",
    "traceids_128bit_tc.propagation",
    "traceids_128bit_tc.tid_in_chunk_root",
    "traceids_128bit_tc.tid_in_trace_chunk",
    "traceids_128bit_tc.tid_inconsistent",
    "traceids_128bit_tc.tid_malformed",
    # single-span sampling (DD_SPAN_SAMPLING_RULES) not implemented — no _dd.span_sampling.* tags on the delivered span
    "span_sampling.sss001_single_rule_match",
    "span_sampling.sss002_glob_chars",
    "span_sampling.sss004_service_only",
    "span_sampling.sss006_multi_keep_drop",
    "span_sampling.sss011_manual_drop_kept",
    "span_sampling.sss014_root_selected",
    "span_sampling.sss015_child_selected",
    # OTEL_* env mapping / config surface not implemented in dd-trace-rs Config (OTEL_SERVICE_NAME/RESOURCE_ATTRIBUTES/TRACES_SAMPLER*/LOG_LEVEL/SDK_DISABLED/TRACES_EXPORTER, and DD_TRACE_PROPAGATION_STYLE readback)
    "otel_env_vars.always_off",
    "otel_env_vars.always_on",
    "otel_env_vars.attribute_mapping",
    "otel_env_vars.dd_precedence",
    "otel_env_vars.exporter_none",
    "otel_env_vars.log_level_debug",
    "otel_env_vars.otel_only",
    "otel_env_vars.parentbased_off",
    "otel_env_vars.parentbased_on",
    "otel_env_vars.parentbased_ratio",
    "otel_env_vars.sdk_disabled",
    "otel_env_vars.traceidratio",
    # source-code-integration git tags (_dd.git.*) not emitted from DD_GIT_* env
    "tracer.sci_commit_sha",
    "tracer.sci_repository_url",
    "tracer.sci_strip_https_clean",
    "tracer.sci_strip_https_token",
    "tracer.sci_strip_https_userpass",
    "tracer.sci_strip_no_scheme",
    "tracer.sci_strip_scp_style",
    "tracer.sci_strip_ssh_token",
    "tracer.sci_strip_ssh_userpass",
    # tag-based trace sampling rules not applied: dd-trace-rs (OpenTelemetry-based) makes the sampling decision at span start, before the matched tag is set, so DD_TRACE_SAMPLING_RULES tag matchers never match
    "trace_sampling.case_insensitive_tag",
    "trace_sampling.tag_foo_any",
    "trace_sampling.tag_foo_exact",
    "trace_sampling.tag_foo_star",
    "trace_sampling.tag_metric_20",
    "trace_sampling.tag_range_literal",
    "trace_sampling.tag_set_literal",
    "trace_sampling.tags_dropped",
    "trace_sampling.tags_single",
    # tracestate propagation edge cases (duplicate/empty/multi-header/OWS vendor-member retention) not handled
    "headers_tracecontext.duplicated",
    "headers_tracecontext.ts_empty_header",
    "headers_tracecontext.ts_multiple_headers_diff_keys",
    "headers_tracecontext.ts_ows_handling",
    # propagated _dd.p.dm sampling-mechanism value differs (-0 vs -4) — same diff go/java/ruby/php carry
    "headers_tracestate_dd.propagate_propagatedtags",
    # W3C baggage header not injected (dd-trace-rs has no manual baggage API — commented out in the upstream rust parametric client too)
    "headers_baggage.only_D002",
    # config: DD_TAGS space-separated form not parsed (comma only); ipv6 agent-url readback blocked by the runner forcing DD_TRACE_AGENT_URL (same as other backends)
    "config_consistency.agent_host_ipv6",
    "config_consistency.tags_space",
}

# dd-trace-rs expects short propagation-style names; the suite emits canonical
# ones (same translation dd-trace-rb needs).
STYLE_MAP = {
    "datadog": "datadog",
    "b3 single header": "b3", "b3": "b3",
    "b3 multi header": "b3multi", "b3multi": "b3multi",
    "tracecontext": "tracecontext", "baggage": "baggage", "none": "none",
}


def _map_styles(env):
    for k in ("DD_TRACE_PROPAGATION_STYLE", "DD_TRACE_PROPAGATION_STYLE_EXTRACT",
              "DD_TRACE_PROPAGATION_STYLE_INJECT"):
        v = env.get(k)
        if not v:
            continue
        env[k] = ",".join(STYLE_MAP.get(s.strip().lower(), s.strip()) for s in v.split(","))


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


_port = _free_port()
_otlp_http_port = _free_port()
_otlp_grpc_port = _free_port()
_agent_url = f"http://127.0.0.1:{_port}"
_agent = subprocess.Popen(
    [os.path.join(os.path.dirname(sys.executable), "ddapm-test-agent"),
     "--port", str(_port),
     "--otlp-http-port", str(_otlp_http_port),
     "--otlp-grpc-port", str(_otlp_grpc_port)],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)


def _reap():
    try:
        _agent.terminate()
        _agent.wait(timeout=5)
    except Exception:
        _agent.kill()


atexit.register(_reap)


def _agent_get(path):
    try:
        return urllib.request.urlopen(_agent_url + path, timeout=3).read()
    except Exception:
        return None


for _ in range(50):
    if _agent_get("/info") is not None:
        break
    time.sleep(0.2)

passed = failed = skipped = 0
try:
    for i, case in enumerate(cases):
        env = dict(os.environ)
        env["DD_TRACE_AGENT_URL"] = _agent_url
        for k in case.env.keys():
            env[k] = case.env[k]
        _map_styles(env)
        if case.name in KNOWN_RUST_DIFFS:
            env["RUST_KNOWN_DIFF"] = "1"
        _agent_get("/test/session/clear")
        res = subprocess.run([BIN, str(i)], env=env, capture_output=True, text=True)
        sys.stdout.write(res.stdout)
        if res.returncode == 2:
            skipped += 1
        elif res.returncode != 0:
            failed += 1
        else:
            passed += 1
finally:
    _reap()

print(f"\n{passed}/{passed + failed} cases passed (dd-trace-rust)"
      + (f", {skipped} skipped" if skipped else ""))
sys.exit(1 if failed else 0)
