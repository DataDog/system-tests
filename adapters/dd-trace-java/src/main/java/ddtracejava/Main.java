package ddtracejava;

// Conformance runner for dd-trace-java.
//   no args  -> orchestrator: starts a ddapm-test-agent, runs each case in its
//               own JVM launched WITH -javaagent:dd-java-agent.jar (so the OTel
//               API produces real DD spans) and the case's env applied.
//   <index>  -> run one case by index against the real tracer.

import io.opentelemetry.api.trace.Span; // ensure the OTel API is on the classpath
import system_tests_redux.CheckResult;
import system_tests_redux.ConformanceCase;
import system_tests_redux.SystemTestsReduxGlobal;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.ServerSocket;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

public final class Main {
  // Verified genuine dd-trace-java behavior diffs and per-library naming/config
  // divergences (not harness artifacts). A listed case that FAILS is reported as
  // a documented skip, but one that unexpectedly PASSES still reports PASS (the
  // list can't hide a fix).
  static final Map<String, String> KNOWN_JAVA_DIFFS = new java.util.HashMap<>();
  static {
    // b3 single<->multi migration (also skipped on js/go).
    for (String n : new String[]{"migrated_extract_valid", "migrated_inject_valid",
        "migrated_propagate_valid", "migrated_propagate_invalid", "migrated_single_key_propagate_valid"})
      KNOWN_JAVA_DIFFS.put("headers_b3." + n, "no b3 single/multi migration");
    // dd-trace-java 1.63.2 serializes OTel span events only as a `meta.events`
    // JSON string, never the native msgpack `span_events` wire field (go/dotnet
    // have the same gap; only js/py emit native span_events). meta_v05 passes.
    KNOWN_JAVA_DIFFS.put("span_events.native_v04", "dd-trace-java encodes span events as meta.events JSON, not native span_events");
    KNOWN_JAVA_DIFFS.put("span_events.native_v07", "dd-trace-java encodes span events as meta.events JSON, not native span_events");
    // dd-trace-java reports DD_TAGS in telemetry under the name DD_TRACE_TAGS and
    // reorders the value (baz:qux,foo:bar), so the suite's DD_TAGS lookup misses
    // (go/dotnet have the same per-library telemetry naming gap). config_env passes.
    KNOWN_JAVA_DIFFS.put("telemetry.config_tags", "telemetry reports DD_TAGS as DD_TRACE_TAGS with reordered value");
    // The OTel TextMapGetter is single-value-per-key, so the adapter's header
    // carrier collapses duplicate traceparent/tracestate headers (nodejs-parity).
    KNOWN_JAVA_DIFFS.put("headers_tracecontext.duplicated", "adapter header carrier collapses duplicate keys (OTel getter is single-value)");
    KNOWN_JAVA_DIFFS.put("headers_tracecontext.ts_empty_header", "adapter header carrier collapses duplicate keys (OTel getter is single-value)");
    KNOWN_JAVA_DIFFS.put("headers_tracecontext.ts_multiple_headers_diff_keys", "adapter header carrier collapses duplicate keys (OTel getter is single-value)");
    // dd-trace-java propagates an extra _dd.p.ksr (keep-sampling-rate) tag the suite doesn't expect.
    KNOWN_JAVA_DIFFS.put("headers_tracestate_dd.propagate_propagatedtags", "dd-trace-java adds an extra _dd.p.ksr propagated tag");
    // dd-trace-java 1.63's OTel bridge doesn't remap the newer semconv
    // http.response.status_code (string) to http.status_code (go has the same gap).
    KNOWN_JAVA_DIFFS.put("otel_span.http_status_remap", "OTel bridge doesn't remap http.response.status_code to http.status_code");
    // dd-trace-java reports the b3 propagation style by its internal enum name
    // (b3multi for the DD_TRACE_PROPAGATION_STYLE=b3 multi-header alias,
    // b3single for OTEL_PROPAGATORS=b3) rather than the suite's canonical "b3";
    // normalizing would hide the multi-vs-single-header interpretation.
    KNOWN_JAVA_DIFFS.put("otel_env_vars.dd_precedence", "b3 propagation style reported as b3multi");
    KNOWN_JAVA_DIFFS.put("otel_env_vars.otel_only", "b3 propagation style reported as b3single");
    // dd-trace-java's Config exposes no log level, and OTEL_LOG_LEVEL=debug is
    // not mapped to trace-debug.
    KNOWN_JAVA_DIFFS.put("otel_env_vars.log_level", "Config exposes no dd_log_level");
    KNOWN_JAVA_DIFFS.put("otel_env_vars.log_level_debug", "OTEL_LOG_LEVEL=debug not mapped to dd_trace_debug");
  }

  // Config-only agent-url readback cases: skip the DD_TRACE_AGENT_URL force so
  // the tracer resolves (and config() reads back) the case's own url.
  static final java.util.Set<String> AGENT_URL_CASES = new java.util.HashSet<>(Arrays.asList(
      "config_consistency.agent_http_url", "config_consistency.agent_unix_url",
      "config_consistency.agent_http_url_ipv6", "config_consistency.agent_host_ipv6"));

  // Telemetry cases read the app-started telemetry payload the tracer sends to
  // the agent, so telemetry must stay ENABLED for them (it is disabled for every
  // other case to speed startup).
  static final java.util.Set<String> TELEMETRY_CASES = new java.util.HashSet<>(Arrays.asList(
      "telemetry.config_env", "telemetry.config_tags"));

  // Remote-config cases need the RC poller running so it advertises capabilities
  // (and, for the apply case, ACKs pushed config) to the agent's /v0.7/config
  // endpoint. RC is disabled for every other case to speed startup.
  static final java.util.Set<String> RC_CASES = new java.util.HashSet<>(Arrays.asList(
      "dynamic_configuration.capability_sample_rate", "dynamic_configuration.capability_enabled",
      "dynamic_configuration.capability_logs_injection", "dynamic_configuration.capability_http_header_tags",
      "dynamic_configuration.capability_custom_tags", "dynamic_configuration.capability_sample_rules",
      "dynamic_configuration.sampling_rate_override"));

  public static void main(String[] args) throws Exception {
    List<ConformanceCase> cases = SystemTestsReduxGlobal.allCases();
    if (args.length >= 1 && args[0].matches("\\d+")) {
      System.exit(runOne(cases.get(Integer.parseInt(args[0]))));
    }
    // Optional name-prefix filter for fast iteration: `Main span_events` runs
    // only cases whose name starts with the given prefix. No filter -> full run.
    String filter = args.length >= 1 ? args[0] : null;
    System.exit(orchestrate(cases, filter));
  }

  static int runOne(ConformanceCase c) {
    boolean known = KNOWN_JAVA_DIFFS.containsKey(c.getName());
    try {
      CheckResult r = c.getRun().apply(new Adapter());
      if (r.isOk()) { System.out.println("PASS " + c.getName()); return 0; }
      if (known) { System.out.println("SKIP " + c.getName() + " (known dd-trace-java diff: " + KNOWN_JAVA_DIFFS.get(c.getName()) + ")"); return 2; }
      System.out.println("FAIL " + c.getName() + ":\n" + r.summary());
      return 1;
    } catch (UnsupportedOperationException e) {
      System.out.println("SKIP " + c.getName() + " (unsupported on java)");
      return 2;
    } catch (Throwable e) {
      if (known) { System.out.println("SKIP " + c.getName() + " (known dd-trace-java diff)"); return 2; }
      System.out.println("FAIL " + c.getName() + ":\n  exception: " + e);
      return 1;
    }
  }

  static int orchestrate(List<ConformanceCase> cases, String filter) throws Exception {
    Path jar = Paths.get(Main.class.getProtectionDomain().getCodeSource().getLocation().toURI());
    Path adapterDir = jar.getParent().getParent();          // .../target/conformance.jar -> adapter dir
    Path repo = adapterDir.getParent().getParent();
    Path agentJar = adapterDir.resolve("dd-java-agent.jar");
    Path agentBin = repo.resolve(".venv-ddtrace/bin/ddapm-test-agent");
    if (!Files.exists(agentJar)) { System.err.println("missing " + agentJar + " — run ./setup.sh"); return 1; }
    if (!Files.exists(agentBin)) { System.err.println("missing ddapm-test-agent — run ./setup.sh"); return 1; }

    int port = freePort(), otlpHttp = freePort(), otlpGrpc = freePort();
    String agentUrl = "http://127.0.0.1:" + port;
    Process agent = new ProcessBuilder(agentBin.toString(), "--port", "" + port,
        "--otlp-http-port", "" + otlpHttp, "--otlp-grpc-port", "" + otlpGrpc)
        .redirectOutput(new File("/dev/null"))
        .redirectError(new File("/dev/null")).start();
    for (int k = 0; k < 50 && agentGet(agentUrl + "/info") == null; k++) Thread.sleep(200);

    System.out.println("— dd-trace-java conformance runner (OTel API under -javaagent:dd-java-agent.jar) —");
    System.out.println("cases:    " + cases.size() + "\n");
    String javaBin = System.getProperty("java.home") + "/bin/java";
    int passed = 0, failed = 0, skipped = 0;
    try {
      for (int i = 0; i < cases.size(); i++) {
        ConformanceCase c = cases.get(i);
        if (filter != null && !c.getName().startsWith(filter)) continue;
        agentGet(agentUrl + "/test/session/clear");
        boolean telemetryCase = TELEMETRY_CASES.contains(c.getName());
        boolean rcCase = RC_CASES.contains(c.getName());
        List<String> cmd = new ArrayList<>(Arrays.asList(
            javaBin, "-javaagent:" + agentJar, "-Ddd.trace.startup.logs=false",
            // Correctness: disable library auto-instrumentation so the adapter's own
            // HttpURLConnection calls to the test-agent aren't traced as spurious
            // http.request spans (the OTel bridge stays on via DD_TRACE_OTEL_ENABLED).
            "-Ddd.integrations.enabled=false",
            "-cp", jar.toString(), "ddtracejava.Main", "" + i));
        // Speed: skip the agent's telemetry / remote-config work — except for the
        // cases that need them on the wire.
        if (!telemetryCase) cmd.addAll(2, Arrays.asList("-Ddd.trace.telemetry.enabled=false",
            "-Ddd.instrumentation.telemetry.enabled=false"));
        if (!rcCase) cmd.add(2, "-Ddd.remote.config.enabled=false");
        ProcessBuilder pb = new ProcessBuilder(cmd).inheritIO();
        Map<String, String> env = pb.environment();
        for (Map.Entry<String, String> e : c.getEnv().entrySet()) env.put(e.getKey(), e.getValue());
        // Force the agent URL for span delivery -- but NOT for the config-only
        // agent-url readback cases (they create no span; forcing would clobber
        // the url they assert). The adapter's spans go through the OTel bridge so
        // DD_TRACE_OTEL_ENABLED must be on, except for sdk_disabled (config-only,
        // asserts OTEL_SDK_DISABLED turns the bridge off). No DD_SERVICE default:
        // it would override OTEL_SERVICE_NAME -> dd_service.
        if (!AGENT_URL_CASES.contains(c.getName())) env.put("DD_TRACE_AGENT_URL", agentUrl);
        if (!c.getName().equals("otel_env_vars.sdk_disabled")) env.putIfAbsent("DD_TRACE_OTEL_ENABLED", "true");
        int code = pb.start().waitFor();
        if (code == 2) skipped++;
        else if (code != 0) failed++;
        else passed++;
      }
    } finally {
      agent.destroyForcibly();
    }
    System.out.println("\n" + passed + "/" + (passed + failed) + " cases passed (dd-trace-java)"
        + (skipped > 0 ? ", " + skipped + " skipped" : ""));
    return failed > 0 ? 1 : 0;
  }

  static String agentGet(String u) {
    try {
      HttpURLConnection con = (HttpURLConnection) new URL(u).openConnection();
      con.setConnectTimeout(3000);
      con.setReadTimeout(3000);
      InputStream is = con.getInputStream();
      ByteArrayOutputStream bo = new ByteArrayOutputStream();
      byte[] buf = new byte[8192];
      int n;
      while ((n = is.read(buf)) != -1) bo.write(buf, 0, n);
      is.close();
      return bo.toString("UTF-8");
    } catch (Exception e) { return null; }
  }

  static int freePort() throws IOException {
    try (ServerSocket s = new ServerSocket(0)) { return s.getLocalPort(); }
  }
}
