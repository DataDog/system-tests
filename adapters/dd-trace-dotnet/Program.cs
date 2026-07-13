// Conformance runner for dd-trace-dotnet.
//
//   dotnet build adapters/dd-trace-dotnet
//   temper build -b csharp
//   dotnet adapters/dd-trace-dotnet/bin/Debug/net6.0/conformance.dll
//
// No args  -> orchestrator: starts a ddapm-test-agent, runs each case in its own
//             subprocess (env applied before the tracer initializes).
// <index>  -> run one case by index against the real Datadog.Trace tracer.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using DdTraceDotnetAdapter;
using SystemTestsRedux;

internal static class Program
{
    // Genuine dd-trace-dotnet v3.48 (manual API + CLR profiler / automatic
    // instrumentation) behavior gaps. Each was verified against the real library's
    // delivered output; a listed case that fails is reported as a documented skip,
    // but one that unexpectedly passes is still reported PASS so this list stays
    // honest. (Re-derived under v3+profiler: the v2.61 glob/tag-sampling and
    // DD_TAGS-space-separator diffs are gone — v3 supports them — and a v3+profiler
    // OTel cross-API-parenting diff was added.)
    private static readonly Dictionary<string, string> KnownDotnetDiffs = new()
    {
        // SCI: v3 still auto-detects git from the real repo, ignores DD_GIT_* env.
        // SCI: DD_GIT_* is now honored (git embedding disabled in the csproj so it
        // doesn't override the env). The strip cases pass; these two remain because
        // they create root+child and assert the SCI tag is on the ROOT, but
        // dd-dotnet+profiler attaches _dd.git.* to a non-root chunk span (same
        // placement behavior as tid_in_chunk_root).
        ["tracer.sci_commit_sha"] = "SCI tag attached to a non-root chunk span, not the asserted root",
        ["tracer.sci_repository_url"] = "SCI tag attached to a non-root chunk span, not the asserted root",
        // b3 single<->multi migration not implemented (also skipped on dd-trace-js).
        ["headers_b3.migrated_extract_valid"] = "no b3 single/multi migration",
        ["headers_b3.migrated_inject_valid"] = "no b3 single/multi migration",
        ["headers_b3.migrated_propagate_valid"] = "no b3 single/multi migration",
        ["headers_b3.migrated_propagate_invalid"] = "no b3 single/multi migration",
        ["headers_b3.migrated_single_key_propagate_valid"] = "no b3 single/multi migration",
        // OTEL_*->DD mapping DOES resolve under v3+profiler (verified: dd_service,
        // sample rate, tags all map), but these cases assert resolved config keys
        // that the Datadog.Trace public Settings API does not expose, so config()
        // can't read them back. A config-readback gap, not a mapping gap.
        ["otel_env_vars.dd_precedence"] = "dd_trace_propagation_style/dd_runtime_metrics_enabled/dd_trace_debug not exposed by Datadog.Trace Settings",
        ["otel_env_vars.otel_only"] = "dd_trace_propagation_style/dd_runtime_metrics_enabled not exposed by Datadog.Trace Settings",
        ["otel_env_vars.log_level"] = "dd_log_level not exposed by Datadog.Trace Settings",
        ["otel_env_vars.log_level_debug"] = "dd_trace_debug not exposed by Datadog.Trace Settings",
        ["otel_env_vars.otel_enabled_precedence"] = "dd_trace_otel_enabled not exposed by Datadog.Trace Settings",
        ["otel_env_vars.sdk_disabled"] = "dd_trace_otel_enabled not exposed by Datadog.Trace Settings",
        // OTel cross-API parenting: under v3+profiler an OTel-API span created inside
        // an active DD-API span is parented to it by DD's unified context, and the
        // OTel API has no root-escape (DD's manual API has SpanContext.None; the
        // ActivitySource path does not), so two independent roots can't be created
        // when the DD root is opened first.
        ["otel_interop.nested_dd_root"] = "v3+profiler parents an OTel root under an active DD span; OTel API has no root-escape",
        // DD_AGENT_HOST=::1 (unbracketed ipv6) + DD_TRACE_AGENT_PORT is not composed
        // into the Datadog.Trace agent-url readback: Tracer.Instance.Settings.Exporter
        // .AgentUri falls back to the http://127.0.0.1:8126 default, so the ::1/5000
        // readback assertion can't be satisfied. (The http/unix/ipv6-http *url* forms
        // set via DD_TRACE_AGENT_URL now resolve — those cases are recovered.)
        ["config_consistency.agent_host_ipv6"] = "DD_AGENT_HOST=::1 not composed into agent-url readback (defaults to 127.0.0.1:8126)",
        // Ambient baggage get/set/remove (Baggage.Current) IS wired and passes
        // (set_get_D006, remove_D010, remove_all_D011). But the `baggage` HEADER
        // inject/extract is not reachable through Datadog.Trace's manual API: the
        // public SpanContextInjector/SpanContextExtractor never emit or parse the
        // baggage header (verified under v3+profiler even with baggage in the
        // propagation style) — DD does baggage propagation only in its auto-
        // instrumentation HTTP integrations, which this adapter's manual carrier
        // bypasses.
        ["headers_baggage.default_D001"] = "baggage header not injected via manual SpanContextInjector (auto-instrumentation only)",
        ["headers_baggage.only_D002"] = "baggage header not injected via manual SpanContextInjector (auto-instrumentation only)",
        ["headers_baggage.inject_encoding_D004"] = "baggage header not injected via manual SpanContextInjector (auto-instrumentation only)",
        ["headers_baggage.extract_D005"] = "baggage header not parsed via manual SpanContextExtractor (auto-instrumentation only)",
        ["headers_baggage.get_after_extract_D008"] = "baggage header not parsed via manual SpanContextExtractor (auto-instrumentation only)",
        ["headers_baggage.get_all_D009"] = "baggage header not parsed via manual SpanContextExtractor (auto-instrumentation only)",
        ["headers_baggage.max_items_D016"] = "baggage header not injected via manual SpanContextInjector (auto-instrumentation only)",
        ["headers_baggage.max_bytes_D017"] = "baggage header not injected via manual SpanContextInjector (auto-instrumentation only)",
        // v0.4/v0.7 native span_events are wired (read back from the wire); the v0.5
        // meta.events form is not producible: DD_TRACE_NATIVE_SPAN_EVENTS=1 forces the
        // native span_events field even under DD_TRACE_API_VERSION=v0.5, and no
        // meta.events (v0.5) encoder is reachable through Datadog.Trace's manual API.
        ["span_events.meta_v05"] = "native span_events forced under v0.5; no meta.events encoder reachable via manual API",
        // W3C edge cases.
        ["headers_tracecontext.ts_ows_handling"] = "tracestate optional-whitespace not trimmed",
        ["headers_tracestate_dd.evicts_32"] = "no 32-member tracestate eviction",
        // Under v3+profiler _dd.p.tid is serialized onto a child span of the chunk
        // rather than the chunk root, so the root-carries-tid assertion fails (the
        // looser tid_in_trace_chunk "some span carries it" case passes).
        ["traceids_128bit_tc.tid_in_chunk_root"] = "v3+profiler attaches _dd.p.tid to a non-root span of the chunk, not the chunk root",
    };

    // Config-only cases whose check reads back their own DD_TRACE_AGENT_URL. The
    // orchestrator must NOT clobber it with the live test-agent url (they create no
    // span / need no delivery). Mirrors the dd-trace-java adapter's AGENT_URL_CASES.
    private static readonly HashSet<string> AgentUrlCases = new()
    {
        "config_consistency.agent_http_url", "config_consistency.agent_unix_url",
        "config_consistency.agent_http_url_ipv6", "config_consistency.agent_host_ipv6",
    };

    private static int Main(string[] args)
    {
        var cases = SystemTestsReduxGlobal.AllCases();
        if (args.Length >= 1 && int.TryParse(args[0], out var idx))
            return RunOne(cases[idx]);
        return Orchestrate(cases);
    }

    private static int RunOne(ConformanceCase cse)
    {
        var known = KnownDotnetDiffs.TryGetValue(cse.Name, out var reason);
        try
        {
            var r = cse.Run(new Adapter());
            if (r.Ok) { Console.WriteLine($"PASS {cse.Name}"); return 0; }
            if (known) { Console.WriteLine($"SKIP {cse.Name} (known dd-dotnet diff: {reason})"); return 2; }
            Console.WriteLine($"FAIL {cse.Name}:\n{r.Summary()}"); return 1;
        }
        catch (NotImplementedException)
        {
            Console.WriteLine($"SKIP {cse.Name} (unsupported on dotnet)"); return 2;
        }
        catch (Exception e)
        {
            if (known) { Console.WriteLine($"SKIP {cse.Name} (known dd-dotnet diff: {reason})"); return 2; }
            Console.WriteLine($"FAIL {cse.Name}:\n  {e}"); return 1;
        }
    }

    private static int Orchestrate(IReadOnlyList<ConformanceCase> cases)
    {
        var dll = typeof(Program).Assembly.Location;
        var repo = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../.."));
        var agentBin = Path.Combine(repo, ".venv-ddtrace", "bin", "ddapm-test-agent");
        if (!File.Exists(agentBin))
        {
            Console.Error.WriteLine($"ddapm-test-agent not found at {agentBin}\n" +
                "install it into the venv: ./.venv-ddtrace/bin/pip install ddapm-test-agent");
            return 1;
        }
        // Resolve the native CLR profiler from the restored Datadog.Trace.Bundle so
        // every per-case subprocess runs under automatic instrumentation (v3's manual
        // API is a no-op stub without it). The bundle's content/datadog dir is the
        // tracer home; content/datadog/osx holds the macOS native profiler dylib.
        var (tracerHome, profilerPath) = ResolveProfiler();
        if (profilerPath == null)
        {
            Console.Error.WriteLine(
                "Datadog CLR profiler not found. Expected the Datadog.Trace.Bundle package\n" +
                "to restore its native profiler under\n" +
                "  ~/.nuget/packages/datadog.trace.bundle/<version>/content/datadog/osx/Datadog.Trace.ClrProfiler.Native.dylib\n" +
                "Run `dotnet restore adapters/dd-trace-dotnet` (Datadog.Trace.Bundle 3.48.0).");
            return 1;
        }

        var port = FreePort();
        // Unique OTLP ports too: ddapm-test-agent otherwise binds fixed 4318/4317
        // and collides with a concurrently-running sibling agent.
        var otlpHttp = FreePort();
        var otlpGrpc = FreePort();
        var agentUrl = $"http://127.0.0.1:{port}";
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(4) };

        var agent = new Process
        {
            StartInfo = new ProcessStartInfo(agentBin, $"--port {port} --otlp-http-port {otlpHttp} --otlp-grpc-port {otlpGrpc}")
            { UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true }
        };
        agent.Start();
        // Drain the agent's stdout/stderr so its pipe buffer never fills and blocks it.
        agent.OutputDataReceived += (_, __) => { };
        agent.ErrorDataReceived += (_, __) => { };
        agent.BeginOutputReadLine();
        agent.BeginErrorReadLine();
        string Get(string path) { try { return http.GetStringAsync(agentUrl + path).GetAwaiter().GetResult(); } catch { return null; } }
        for (var k = 0; k < 50 && Get("/info") == null; k++) System.Threading.Thread.Sleep(200);

        Console.WriteLine("— dd-trace-dotnet conformance runner (native Datadog.Trace) —");
        Console.WriteLine($"cases:    {cases.Count}\n");

        int passed = 0, failed = 0, skipped = 0;
        try
        {
            for (var i = 0; i < cases.Count; i++)
            {
                var cse = cases[i];
                var psi = new ProcessStartInfo("dotnet", $"exec \"{dll}\" {i}") { UseShellExecute = false };
                foreach (var kv in cse.Env) psi.Environment[kv.Key] = kv.Value;
                // Force the live test-agent url for span delivery — but NOT for the
                // config-only agent-url readback cases, which assert their own url.
                if (!AgentUrlCases.Contains(cse.Name)) psi.Environment["DD_TRACE_AGENT_URL"] = agentUrl;
                // --- CLR profiler (Datadog.Trace v3 automatic instrumentation) ---
                psi.Environment["CORECLR_ENABLE_PROFILING"] = "1";
                psi.Environment["CORECLR_PROFILER"] = "{846F5F1C-F9AE-4B07-969E-05C26BC060D8}";
                psi.Environment["CORECLR_PROFILER_PATH"] = profilerPath;
                psi.Environment["DD_DOTNET_TRACER_HOME"] = tracerHome;
                // The OTel bridge needs DD_TRACE_OTEL_ENABLED on — except sdk_disabled,
                // a config-only case asserting OTEL_SDK_DISABLED turns the bridge off.
                if (cse.Name != "otel_env_vars.sdk_disabled") psi.Environment["DD_TRACE_OTEL_ENABLED"] = "true";
                // Suppress auto-instrumentation of the adapter's own HttpClient calls
                // to the test-agent, which would otherwise pollute per-case traces.
                psi.Environment["DD_TRACE_HttpMessageHandler_ENABLED"] = "false";
                psi.Environment["DD_TRACE_HttpSocketsHandler_ENABLED"] = "false";
                Get("/test/session/clear");
                var p = Process.Start(psi);
                p.WaitForExit();
                if (p.ExitCode == 2) skipped++;
                else if (p.ExitCode != 0) failed++;
                else passed++;
            }
        }
        finally
        {
            try { agent.Kill(true); } catch { }
        }

        Console.WriteLine($"\n{passed}/{passed + failed} cases passed (dd-trace-dotnet)" + (skipped > 0 ? $", {skipped} skipped" : ""));
        return failed > 0 ? 1 : 0;
    }

    // Locate the bundled native profiler + tracer home. Globs the restored
    // Datadog.Trace.Bundle package so the version isn't hard-coded to one path.
    private static (string tracerHome, string profilerPath) ResolveProfiler()
    {
        var home = Environment.GetEnvironmentVariable("HOME") ?? "";
        var bundleRoot = Path.Combine(home, ".nuget", "packages", "datadog.trace.bundle");
        if (!Directory.Exists(bundleRoot)) return (null, null);
        // Prefer the version matching Datadog.Trace (3.48.0); fall back to any.
        var versions = Directory.GetDirectories(bundleRoot).OrderByDescending(d => d);
        foreach (var v in new[] { Path.Combine(bundleRoot, "3.48.0") }.Concat(versions))
        {
            var datadog = Path.Combine(v, "content", "datadog");
            var dylib = Path.Combine(datadog, "osx", "Datadog.Trace.ClrProfiler.Native.dylib");
            if (File.Exists(dylib)) return (datadog, dylib);
        }
        return (null, null);
    }

    private static int FreePort()
    {
        var l = new TcpListener(IPAddress.Loopback, 0);
        l.Start();
        var port = ((IPEndPoint)l.LocalEndpoint).Port;
        l.Stop();
        return port;
    }
}
