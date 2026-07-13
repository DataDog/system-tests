<?php
// Conformance runner for dd-trace-php.
//
//   temper build -b py                       # generate the Temper registry (Python)
//   bash adapters/dd-trace-ruby/build.sh     # build the shared rust cdylib
//   /opt/homebrew/opt/php/bin/php adapters/dd-trace-php/run.php
//
// Drives the real ddtrace extension (shared rust cdylib + PHP FFI) with the
// Temper suite. Each case runs in its own subprocess (run_one.php) so its DD_*
// env is applied before the extension initializes; spans go to one shared
// ddapm-test-agent and are read back via /test/session/traces.
//
// The case env is sourced from the Python registry (all_cases() in temper.out/py)
// the same way the dd-trace-go/ruby runners do — the rust cdylib and the Python
// registry are compiled from the same src/, so case ordering matches.

$HERE = __DIR__;
$REPO = dirname($HERE, 2);
$PHP = PHP_BINARY;
$PY = "$REPO/.venv-ddtrace/bin/python";
$LIBRARY = "php";

// Verified genuine dd-trace-php behavior/config diffs (each mirrors a diff other
// backends also carry). A listed case that unexpectedly PASSES still reports
// PASS (run_one.php only downgrades a genuine FAIL), so the list can't hide a fix.
$KNOWN_PHP_DIFFS = [
    // Extraction style-order: with "datadog,tracecontext" + EXTRACT_FIRST=true,
    // dd-trace-php extracts tracecontext (parent 15) rather than datadog first
    // (verified via a direct consume_distributed_tracing_headers probe).
    "headers_tracecontext.p3_extract_first" => "extract-first doesn't honor datadog-before-tracecontext order",
    "headers_precedence.tc_last_extract_first_true" => "extract-first style-order drops tracestate members",
    // tracestate optional-whitespace (OWS) around values is not stripped (as dotnet).
    "headers_tracecontext.ts_ows_handling" => "tracestate OWS not stripped",
    // propagated _dd.p.dm sampling-mechanism value differs (-0 vs -4), as ruby/go/java.
    "headers_tracestate_dd.propagate_propagatedtags" => "_dd.p.dm mechanism value differs",
    // dd-trace-php truncates tracestate to 31 list-members (not 32).
    "headers_tracestate_dd.keeps_32" => "tracestate truncated to 31 list-members",
    "headers_tracestate_dd.evicts_32" => "tracestate truncated to 31 list-members",
    // partial-flush chunk sampling-priority/placement differs.
    "partial_flushing.one_span" => "partial-flush chunk carries priority 0 (behavior differs)",
    // config-surface gaps: DD_RUNTIME_METRICS_ENABLED isn't implemented in PHP,
    // and OTEL_LOG_LEVEL=debug isn't mapped to the dd_trace_debug flag.
    "otel_env_vars.dd_precedence" => "DD_RUNTIME_METRICS_ENABLED not implemented in dd-trace-php",
    "otel_env_vars.log_level_debug" => "OTEL_LOG_LEVEL=debug not mapped to dd_trace_debug",
    // OTel bridge behavior diffs (verified against real dd-trace-php; both also
    // carried by the java backend):
    "otel_env_vars.sdk_disabled" => "OTEL_SDK_DISABLED not honored in the config surface",
    "otel_span.http_status_remap" => "OTel http.response.status_code not remapped to http.status_code",
    // runner forces DD_TRACE_AGENT_URL for delivery, so the DD_AGENT_HOST/PORT
    // (ipv6) agent-url readback can't be tested (same as ruby/go/dotnet).
    "config_consistency.agent_host_ipv6" => "runner forces DD_TRACE_AGENT_URL for span delivery",
];

// --- source per-case name/env/unsupported from the Python registry -----------
$CASES_SCRIPT = <<<'PY'
import sys, os, json
repo = os.environ["REPO"]
sys.path[:0] = [os.path.join(repo, "temper.out", "py", p)
                for p in ("system-tests-redux", "temper-core", "std")]
from system_tests_redux.system_tests_redux import all_cases
out = []
for c in all_cases():
    out.append({
        "name": c.name,
        "env": dict(c.env),
        "unsupported": list(c.unsupported),
        "needs_agent": bool(getattr(c, "needs_agent", False)),
    })
print(json.dumps(out))
PY;

function load_cases(string $PY, string $CASES_SCRIPT, string $REPO): array
{
    $desc = [1 => ["pipe", "w"], 2 => ["pipe", "w"]];
    $proc = proc_open([$PY, "-c", $CASES_SCRIPT], $desc, $pipes, null, ["REPO" => $REPO] + $_ENV + getenv());
    $out = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    $err = stream_get_contents($pipes[2]);
    fclose($pipes[2]);
    $rc = proc_close($proc);
    if ($rc !== 0) {
        fwrite(STDERR, "failed to load case registry (is temper.out/py built? run: temper build -b py)\n$err\n");
        exit(1);
    }
    return json_decode($out, true);
}

function free_port(): int
{
    $s = stream_socket_server("tcp://127.0.0.1:0", $errno, $errstr);
    $name = stream_socket_get_name($s, false);
    fclose($s);
    return (int) substr($name, strrpos($name, ":") + 1);
}

function agent_get(string $base, string $path): ?string
{
    $ch = curl_init($base . $path);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 3, CURLOPT_CONNECTTIMEOUT => 2]);
    $body = curl_exec($ch);
    curl_close($ch);
    return $body === false ? null : $body;
}

$cases = load_cases($PY, $CASES_SCRIPT, $REPO);

echo "— dd-trace-php conformance runner (PHP FFI -> shared rust cdylib) —\n";
$phpVer = trim(shell_exec("$PHP --version 2>/dev/null | head -1"));
$ddVer = trim(shell_exec("DD_TRACE_CLI_ENABLED=1 $PHP -r 'echo phpversion(\"ddtrace\");' 2>/dev/null"));
echo "php:      $phpVer\n";
echo "ddtrace:  $ddVer\n";
echo "cases:    " . count($cases) . "\n\n";

// --- one shared ddapm-test-agent on unique ports -----------------------------
$port = free_port();
$otlpHttp = free_port();
$otlpGrpc = free_port();
$agentUrl = "http://127.0.0.1:$port";
$agentBin = "$REPO/.venv-ddtrace/bin/ddapm-test-agent";

$agentProc = proc_open(
    [$agentBin, "--port", (string) $port, "--otlp-http-port", (string) $otlpHttp, "--otlp-grpc-port", (string) $otlpGrpc],
    [1 => ["file", "/dev/null", "w"], 2 => ["file", "/dev/null", "w"]],
    $agentPipes
);
register_shutdown_function(function () use ($agentProc) {
    if (is_resource($agentProc)) { proc_terminate($agentProc); }
});

for ($i = 0; $i < 50; $i++) {
    if (agent_get($agentUrl, "/info") !== null) { break; }
    usleep(200000);
}

// dd-trace-php's accepted propagation style names differ per style: it wants the
// LONG "B3 single header" but the SHORT "b3multi" (verified empirically). The
// shared cases use the system-tests canonical tokens; translate (as py/go/ruby do).
$style_map = [
    "datadog" => "datadog",
    "tracecontext" => "tracecontext",
    "b3" => "B3 single header", "b3 single header" => "B3 single header",
    "b3multi" => "b3multi", "b3 multi header" => "b3multi",
    "baggage" => "baggage", "none" => "none",
];

$passed = $failed = $skipped = 0;
foreach ($cases as $i => $c) {
    if (in_array($LIBRARY, $c["unsupported"], true)) {
        echo "SKIP {$c['name']} (unsupported on $LIBRARY)\n";
        $skipped++;
        continue;
    }

    $env = getenv();
    $env["DD_TRACE_AGENT_URL"] = $agentUrl;
    $env["DD_TRACE_CLI_ENABLED"] = "1";          // trace the CLI SAPI process
    $env["DD_TRACE_GENERATE_ROOT_SPAN"] = "0";   // we manage roots via start_trace_span
    $env["DD_TRACE_SIDECAR_TRACE_SENDER"] = "0"; // legacy sender (sidecar times out on macOS)
    $env["DD_TRACE_OTEL_ENABLED"] = "1";         // bridge OTel-API spans -> DD spans
    foreach ($c["env"] as $k => $v) { $env[$k] = $v; }

    foreach (["DD_TRACE_PROPAGATION_STYLE", "DD_TRACE_PROPAGATION_STYLE_EXTRACT", "DD_TRACE_PROPAGATION_STYLE_INJECT"] as $k) {
        if (!isset($env[$k])) { continue; }
        $parts = array_map(function ($s) use ($style_map) {
            $t = strtolower(trim($s));
            return $style_map[$t] ?? trim($s);
        }, explode(",", $env[$k]));
        $env[$k] = implode(",", $parts);
    }

    if (isset($KNOWN_PHP_DIFFS[$c["name"]])) { $env["PHP_KNOWN_DIFF"] = "1"; }

    agent_get($agentUrl, "/test/session/clear");

    $desc = [1 => ["pipe", "w"], 2 => ["pipe", "w"]];
    $proc = proc_open([$PHP, "$HERE/run_one.php", (string) $i], $desc, $pipes, $HERE, $env);
    $out = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $status = proc_close($proc);

    echo $out;
    if ($status === 2) {
        $skipped++;
    } elseif ($status === 0) {
        $passed++;
    } else {
        $failed++;
    }
}

$ran = $passed + $failed;
$tail = $skipped > 0 ? ", $skipped skipped" : "";
echo "\n$passed/$ran cases passed (dd-trace-php)$tail\n";
exit($failed === 0 ? 0 : 1);
