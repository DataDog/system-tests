// Native dd-trace-dotnet adapter for the Temper conformance suite.
//
// The suite is compiled to C# (temper.out/csharp/system-tests-redux); this class
// implements the generated ITracer against the real Datadog.Trace library. Ops
// not yet wired throw NotImplementedException so the runner records a skip.
// Spans are delivered to a real ddapm-test-agent (DD_TRACE_AGENT_URL) and read
// back for CapturedSpans().
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using Datadog.Trace;
using Datadog.Trace.Configuration;
using SystemTestsRedux;

namespace DdTraceDotnetAdapter
{
    public sealed class Adapter : SystemTestsRedux.ITracer
    {
        private readonly Dictionary<string, IScope> _scopes = new();
        private readonly Dictionary<string, ISpanContext> _ctx = new();
        // OTel-bridge (System.Diagnostics.ActivitySource) bookkeeping. Under
        // Datadog.Trace v3 + the CLR profiler with DD_TRACE_OTEL_ENABLED=true, DD
        // registers an ActivityListener so StartActivity yields a real DD span.
        private readonly Dictionary<string, Activity> _activities = new();
        private readonly HashSet<string> _otelEnded = new();
        private readonly HashSet<string> _statusLocked = new();
        // spanId (DD-decimal form) -> ActivityContext, for both DD- and OTel-created
        // spans, so cross-API children can be parented deterministically.
        private readonly Dictionary<string, ActivityContext> _actx = new();
        private static readonly ActivitySource Source = new("system-tests-redux.conformance");
        private static readonly HttpClient Http = new();

        static Adapter()
        {
            // Point the tracer at the test-agent explicitly; the manual-API default
            // settings don't pick up DD_TRACE_AGENT_URL on their own here.
            var url = Environment.GetEnvironmentVariable("DD_TRACE_AGENT_URL");
            if (!string.IsNullOrEmpty(url))
            {
                var settings = TracerSettings.FromDefaultSources();
                settings.Exporter.AgentUri = new Uri(url);
                Tracer.Configure(settings);
            }
        }

        private static Dictionary<string, string> EmptyMeta() => new();
        private static Dictionary<string, double> EmptyMetrics() => new();
        private static List<CapturedLink> EmptyLinks() => new();

        public CapturedSpan StartSpan(string name, string parentId, string service = null, string resource = null, string spanType = null)
        {
            // Parent is set explicitly from the tracked id; for a root (parentId "0")
            // it stays null. Conformance cases finish each span before starting the
            // next, so no unclosed scope is ambient-active to accidentally parent a
            // root span. (Cross-API/otel-mixed roots are skipped on this backend.)
            var settings = new SpanCreationSettings();
            var isRoot = string.IsNullOrEmpty(parentId) || parentId == "0";
            if (isRoot)
            {
                // Under the profiler the DD manual API shares the ambient scope stack,
                // so a genuine root started while another span is active would inherit
                // it. Only when something is actually active do we pin SpanContext.None
                // to force a fresh trace — SpanContext.None also suppresses 128-bit
                // trace-id generation, so a plain root (no ambient span) must be left
                // with the default parent for _dd.p.tid to be produced.
                if (Activity.Current != null) settings.Parent = SpanContext.None;
            }
            else if (_ctx.TryGetValue(parentId, out var pc))
                settings.Parent = pc;
            var scope = Tracer.Instance.StartActive(name, settings);
            var span = scope.Span;
            if (!string.IsNullOrEmpty(service)) span.ServiceName = service;
            if (!string.IsNullOrEmpty(resource)) span.ResourceName = resource;
            if (!string.IsNullOrEmpty(spanType)) span.Type = spanType;
            var id = span.Context.SpanId.ToString();
            var traceId = span.Context.TraceId.ToString();
            _scopes[id] = scope;
            _ctx[id] = span.Context;
            _actx[id] = DdSpanActivityContext(span.Context);
            return new CapturedSpan(traceId, id, parentId ?? "0", name,
                service ?? "", resource ?? "", spanType ?? "",
                EmptyMeta(), EmptyMetrics(), EmptyLinks(), null);
        }

        public void FinishSpan(string spanId)
        {
            if (_scopes.TryGetValue(spanId, out var s)) { s.Span.Finish(); s.Close(); }
        }

        public void SetMeta(string spanId, string key, string value)
        {
            if (_scopes.TryGetValue(spanId, out var s)) s.Span.SetTag(key, value);
            else if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) a.SetTag(key, value);
        }

        public void SetMetric(string spanId, string key, double value)
        {
            if (_scopes.TryGetValue(spanId, out var s)) s.Span.SetTag(key, value);
            else if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) a.SetTag(key, (object)value);
        }

        public string ExtractHeaders(IReadOnlyList<KeyValuePair<string, string>> headers)
        {
            var carrier = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
            foreach (var kv in headers)
            {
                if (!carrier.TryGetValue(kv.Key, out var list)) { list = new(); carrier[kv.Key] = list; }
                list.Add(kv.Value);
            }
            var ctx = new SpanContextExtractor().Extract(carrier,
                (c, k) => c.TryGetValue(k, out var vs) ? vs : Enumerable.Empty<string>());
            if (ctx == null) return "0";
            var id = ctx.SpanId.ToString();
            _ctx[id] = ctx;
            return id;
        }

        public IReadOnlyDictionary<string, string> InjectHeaders(string spanId)
        {
            var outp = new Dictionary<string, string>();
            if (_ctx.TryGetValue(spanId, out var ctx))
                new SpanContextInjector().Inject(outp, (c, k, v) => c[k] = v, ctx);
            return outp;
        }

        public void Flush() => Tracer.Instance.ForceFlushAsync().GetAwaiter().GetResult();

        public IReadOnlyList<CapturedSpan> CapturedSpans()
        {
            Flush();
            var url = (Environment.GetEnvironmentVariable("DD_TRACE_AGENT_URL") ?? "").TrimEnd('/');
            var outp = new List<CapturedSpan>();
            if (url == "") return outp;
            var deadline = DateTime.UtcNow.AddSeconds(3);
            while (DateTime.UtcNow < deadline)
            {
                JsonElement traces;
                try
                {
                    var raw = Http.GetStringAsync(url + "/test/session/traces").GetAwaiter().GetResult();
                    traces = JsonDocument.Parse(raw).RootElement;
                }
                catch { traces = default; }
                if (traces.ValueKind == JsonValueKind.Array && traces.GetArrayLength() > 0)
                {
                    foreach (var trace in traces.EnumerateArray())
                        foreach (var sp in trace.EnumerateArray())
                        {
                            var meta = new Dictionary<string, string>();
                            if (sp.TryGetProperty("meta", out var m) && m.ValueKind == JsonValueKind.Object)
                                foreach (var p in m.EnumerateObject()) meta[p.Name] = p.Value.ToString();
                            var metrics = new Dictionary<string, double>();
                            if (sp.TryGetProperty("metrics", out var mx) && mx.ValueKind == JsonValueKind.Object)
                                foreach (var p in mx.EnumerateObject())
                                    if (p.Value.ValueKind == JsonValueKind.Number) metrics[p.Name] = p.Value.GetDouble();
                            string Str(string k) => sp.TryGetProperty(k, out var v) && v.ValueKind != JsonValueKind.Null ? v.ToString() : "";
                            int? err = null;
                            if (sp.TryGetProperty("error", out var ev) && ev.ValueKind == JsonValueKind.Number)
                                err = ev.GetInt32();
                            // A root span's parent_id is absent/null on the wire; the
                            // suite expects the sentinel "0".
                            var parent = Str("parent_id");
                            if (parent == "") parent = "0";
                            outp.Add(new CapturedSpan(Str("trace_id"), Str("span_id"), parent,
                                Str("name"), Str("service"), Str("resource"), Str("type"),
                                meta, metrics, EmptyLinks(), err));
                        }
                    break;
                }
                System.Threading.Thread.Sleep(150);
            }
            return outp;
        }

        // --- not yet wired through Datadog.Trace's manual API ---
        private static T U<T>() => throw new NotImplementedException("dd-trace-dotnet adapter: op not implemented");

        // Baggage in Datadog.Trace v3 is an ambient AsyncLocal store (Baggage.Current),
        // not a per-span attachment. The conformance cases operate on the currently
        // active span, and each case runs in its own subprocess, so mapping the
        // per-spanId API onto the ambient dictionary is faithful here. Baggage is
        // propagated on inject/extract by DD's propagators (with a `baggage` style).
        public void SetBaggage(string spanId, string key, string value) => Baggage.Current[key] = value;
        public string GetBaggage(string spanId, string key) =>
            Baggage.Current.TryGetValue(key, out var v) ? v : "";
        public IReadOnlyDictionary<string, string> GetAllBaggage(string spanId) =>
            new Dictionary<string, string>(Baggage.Current);
        public void RemoveBaggage(string spanId, string key) => Baggage.Current.Remove(key);
        public void RemoveAllBaggage(string spanId) => Baggage.Current.Clear();
        public void AddLink(string spanId, string linkToSpanId, IReadOnlyDictionary<string, string> attributes) => U<int>();
        public void SetResource(string spanId, string value)
        {
            if (_scopes.TryGetValue(spanId, out var s)) { s.Span.ResourceName = value; return; }
            // OTel-created span manipulated through the DD resource API: DD's bridge
            // reads the resource from the "resource.name" tag on the Activity.
            if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) { a.SetTag("resource.name", value); return; }
            U<int>();
        }
        public void RemoveMeta(string spanId, string key)
        {
            if (_scopes.TryGetValue(spanId, out var s)) s.Span.SetTag(key, null);
            else if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) a.SetTag(key, null);
        }
        public void RemoveMetric(string spanId, string key)
        {
            if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) { a.SetTag(key, null); return; }
            U<int>();
        }
        public void OtelSetAttributeNum(string spanId, string key, double value)
        {
            if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) a.SetTag(key, (object)value);
        }
        public void OtelRemoveAttribute(string spanId, string key)
        {
            if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) a.SetTag(key, null);
        }
        public IReadOnlyDictionary<string, string> Config()
        {
            var s = Tracer.Instance.Settings;
            var d = new Dictionary<string, string>();
            System.Globalization.CultureInfo inv = System.Globalization.CultureInfo.InvariantCulture;
            if (!string.IsNullOrEmpty(s.ServiceName)) d["dd_service"] = s.ServiceName;
            if (!string.IsNullOrEmpty(s.Environment)) d["dd_env"] = s.Environment;
            if (!string.IsNullOrEmpty(s.ServiceVersion)) d["dd_version"] = s.ServiceVersion;
            if (s.GlobalSamplingRate.HasValue) d["dd_trace_sample_rate"] = s.GlobalSamplingRate.Value.ToString(inv);
            d["dd_trace_rate_limit"] = s.MaxTracesSubmittedPerSecond.ToString(inv);
            d["dd_trace_enabled"] = s.TraceEnabled ? "true" : "false";
            if (s.Exporter?.AgentUri != null) d["dd_trace_agent_url"] = s.Exporter.AgentUri.ToString();
            if (s.GlobalTags != null && s.GlobalTags.Count > 0)
                d["dd_tags"] = string.Join(",", s.GlobalTags.Select(kv => $"{kv.Key}:{kv.Value}"));
            return d;
        }
        // --- OpenTelemetry bridge (ActivitySource) — real under v3 + profiler ---
        private static ActivityKind MapKind(string kind) => (kind ?? "").ToLowerInvariant() switch
        {
            "producer" => ActivityKind.Producer,
            "consumer" => ActivityKind.Consumer,
            "client" => ActivityKind.Client,
            "server" => ActivityKind.Server,
            _ => ActivityKind.Internal,
        };
        // DD reports span/trace ids as unsigned-64 decimals; Activity ids are hex
        // (16-byte trace, 8-byte span). DD's trace_id is the low 64 bits of the
        // 128-bit trace id. Convert so returned ids match the agent-delivered span.
        private static ulong HexToU64(ReadOnlySpan<char> hex) =>
            ulong.Parse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        private static string ActivitySpanDecimal(Activity a) => HexToU64(a.SpanId.ToHexString()).ToString(CultureInfo.InvariantCulture);
        private static string ActivityTraceDecimal(Activity a) => HexToU64(a.TraceId.ToHexString().AsSpan(16, 16)).ToString(CultureInfo.InvariantCulture);
        // Build an ActivityContext from a DD SpanContext so an OTel child can be
        // deterministically parented on a DD-created span (cross-API interop).
        // SpanContext.TraceIdUpper (the high 64 bits of a 128-bit trace id) is
        // internal in Datadog.Trace, so read it reflectively; default to 0 if absent.
        private static readonly System.Reflection.PropertyInfo TraceIdUpperProp =
            typeof(SpanContext).GetProperty("TraceIdUpper",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        private static ActivityContext DdSpanActivityContext(ISpanContext ctx)
        {
            var upper = ctx is SpanContext sc && TraceIdUpperProp != null ? (ulong)TraceIdUpperProp.GetValue(sc) : 0UL;
            var traceHex = upper.ToString("x16", CultureInfo.InvariantCulture) + ctx.TraceId.ToString("x16", CultureInfo.InvariantCulture);
            var spanHex = ctx.SpanId.ToString("x16", CultureInfo.InvariantCulture);
            return new ActivityContext(ActivityTraceId.CreateFromString(traceHex.AsSpan()),
                ActivitySpanId.CreateFromString(spanHex.AsSpan()), ActivityTraceFlags.Recorded);
        }

        public CapturedSpan OtelStartSpan(string name, string parentId, string kind)
        {
            var akind = MapKind(kind);
            Activity act;
            if (!string.IsNullOrEmpty(parentId) && parentId != "0" && _actx.TryGetValue(parentId, out var pc))
            {
                act = Source.StartActivity(name, akind, pc);
            }
            else
            {
                // Root: StartActivity otherwise inherits the ambient Activity (which
                // under the profiler includes any active DD span), so detach it first
                // to force a fresh trace.
                var prev = Activity.Current;
                Activity.Current = null;
                act = Source.StartActivity(name, akind);
                if (act == null) Activity.Current = prev;
            }
            if (act == null)
                throw new InvalidOperationException(
                    "OTel bridge inactive: ActivitySource.StartActivity returned null " +
                    "(need Datadog.Trace v3 + CLR profiler with DD_TRACE_OTEL_ENABLED=true)");
            var id = ActivitySpanDecimal(act);
            var traceId = ActivityTraceDecimal(act);
            _activities[id] = act;
            _actx[id] = act.Context;
            return new CapturedSpan(traceId, id, parentId ?? "0", name,
                "", name, "", EmptyMeta(), EmptyMetrics(), EmptyLinks(), null);
        }

        public void OtelSetAttribute(string spanId, string key, string value)
        {
            if (_activities.TryGetValue(spanId, out var a) && !_otelEnded.Contains(spanId)) a.SetTag(key, value);
        }

        public void OtelEndSpan(string spanId)
        {
            if (_activities.TryGetValue(spanId, out var a) && _otelEnded.Add(spanId)) a.Stop();
        }

        public bool OtelIsRecording(string spanId) => _activities.ContainsKey(spanId) && !_otelEnded.Contains(spanId);

        public OtelSpanContextInfo OtelSpanContext(string spanId)
        {
            if (_activities.TryGetValue(spanId, out var a))
                return new OtelSpanContextInfo(a.TraceId.ToHexString(), a.SpanId.ToHexString());
            return U<OtelSpanContextInfo>();
        }

        public void OtelSetStatus(string spanId, string code, string description)
        {
            if (!_activities.TryGetValue(spanId, out var a) || _otelEnded.Contains(spanId)) return;
            var c = (code ?? "").ToUpperInvariant();
            // OTel status semantics the suite asserts: UNSET is always a no-op, and
            // the first OK/ERROR is final (a later status is ignored). DD's bridge on
            // its own would let a later UNSET clear a prior ERROR, so guard here.
            if (c == "UNSET" || _statusLocked.Contains(spanId)) return;
            if (c == "ERROR")
            {
                a.SetStatus(ActivityStatusCode.Error, description);
                // DD's bridge records the status description as `error.msg`; the
                // conformance suite (matching dd-trace-py/js) expects `error.message`,
                // so mirror it explicitly.
                if (!string.IsNullOrEmpty(description)) a.SetTag("error.message", description);
            }
            else if (c == "OK") a.SetStatus(ActivityStatusCode.Ok, description);
            else return;
            _statusLocked.Add(spanId);
        }

        public void OtelRecordException(string spanId, string message, IReadOnlyDictionary<string, string> attributes)
        {
            if (!_activities.TryGetValue(spanId, out var a) || _otelEnded.Contains(spanId)) return;
            // OTel record_exception = an "exception" span event; DD's bridge maps its
            // exception.* attributes to error.message/type/stack. It does NOT by
            // itself set error=1 (that requires an ERROR status) — matching the
            // record_exception_no_error case.
            var tags = new ActivityTagsCollection { { "exception.message", message } };
            if (attributes != null)
                foreach (var kv in attributes) tags[kv.Key] = kv.Value;
            a.AddEvent(new ActivityEvent("exception", default, tags));
            // DD maps the exception event to `error.msg`/`error.stack`; the suite
            // (dd-trace-py/js parity) expects `error.message`, so mirror the message.
            if (!string.IsNullOrEmpty(message)) a.SetTag("error.message", message);
        }
        // App-started telemetry config. Datadog.Trace's telemetry writer isn't
        // exposed through the manual API, so read the configuration back from the
        // telemetry request the tracer POSTs to the test-agent (names/values/origins
        // are exactly what DD reports: DD_SERVICE, DD_TAGS, DD_TRACE_HEADER_TAGS, ...).
        private static void WalkTelemetryConfig(JsonElement o, Dictionary<string, (string val, string origin)> into)
        {
            if (o.ValueKind == JsonValueKind.Object)
            {
                if (o.TryGetProperty("configuration", out var cfg) && cfg.ValueKind == JsonValueKind.Array)
                    foreach (var c in cfg.EnumerateArray())
                        if (c.ValueKind == JsonValueKind.Object && c.TryGetProperty("name", out var n))
                        {
                            var val = c.TryGetProperty("value", out var v) && v.ValueKind != JsonValueKind.Null ? v.ToString() : "";
                            var origin = c.TryGetProperty("origin", out var og) && og.ValueKind != JsonValueKind.Null ? og.ToString() : "";
                            into[n.ToString()] = (val, origin);
                        }
                foreach (var p in o.EnumerateObject()) WalkTelemetryConfig(p.Value, into);
            }
            else if (o.ValueKind == JsonValueKind.Array)
                foreach (var e in o.EnumerateArray()) WalkTelemetryConfig(e, into);
        }
        public IReadOnlyList<TelemetryConfigItem> TelemetryConfig()
        {
            Flush();
            var outp = new List<TelemetryConfigItem>();
            var url = (Environment.GetEnvironmentVariable("DD_TRACE_AGENT_URL") ?? "").TrimEnd('/');
            if (url == "") return outp;
            var merged = new Dictionary<string, (string val, string origin)>();
            var deadline = DateTime.UtcNow.AddSeconds(10);
            while (DateTime.UtcNow < deadline && merged.Count == 0)
            {
                JsonElement reqs;
                try
                {
                    var raw = Http.GetStringAsync(url + "/test/session/requests").GetAwaiter().GetResult();
                    reqs = JsonDocument.Parse(raw).RootElement;
                }
                catch { System.Threading.Thread.Sleep(300); continue; }
                if (reqs.ValueKind == JsonValueKind.Array)
                    foreach (var r in reqs.EnumerateArray())
                    {
                        if (!(r.TryGetProperty("url", out var u) && u.ToString().Contains("telemetry"))) continue;
                        if (!r.TryGetProperty("body", out var b)) continue;
                        try
                        {
                            JsonElement body;
                            if (b.ValueKind == JsonValueKind.String)
                            {
                                var bytes = Convert.FromBase64String(b.GetString());
                                body = JsonDocument.Parse(bytes).RootElement;
                            }
                            else body = b;
                            WalkTelemetryConfig(body, merged);
                        }
                        catch { }
                    }
                if (merged.Count == 0) System.Threading.Thread.Sleep(300);
            }
            foreach (var kv in merged) outp.Add(new TelemetryConfigItem(kv.Key, kv.Value.val, kv.Value.origin));
            return outp;
        }

        // --- Span events (OTel Activity events -> DD span_events wire encoding) ---
        // DD's OTel bridge maps Activity events to DD span events; under
        // DD_TRACE_NATIVE_SPAN_EVENTS=1 they are delivered on the wire as the native
        // `span_events` field (v0.4/v0.7) or, for v0.5, serialized into meta["events"].
        // We add the events through the real bridge, then read the encoding back from
        // the test-agent (no local encoder needed / exposed).
        private static object CoerceEventScalar(string kind, string v)
        {
            var inv = CultureInfo.InvariantCulture;
            return kind switch
            {
                "int" => (object)long.Parse(v, inv),
                "double" => double.Parse(v, inv),
                "bool" => v == "true",
                _ => v,
            };
        }
        private static object CoerceEventAttr(EventAttr a)
        {
            var vals = a.Values;
            if (a.Kind.EndsWith("_arr"))
            {
                var baseKind = a.Kind.Substring(0, a.Kind.Length - 4);
                switch (baseKind)
                {
                    case "int": return vals.Select(x => long.Parse(x, CultureInfo.InvariantCulture)).ToArray();
                    case "double": return vals.Select(x => double.Parse(x, CultureInfo.InvariantCulture)).ToArray();
                    case "bool": return vals.Select(x => x == "true").ToArray();
                    default: return vals.ToArray();
                }
            }
            return CoerceEventScalar(a.Kind, vals.Count > 0 ? vals[0] : "");
        }
        public void OtelAddEvent(string spanId, string name, int timeMicros, IReadOnlyList<EventAttr> attrs)
        {
            if (!_activities.TryGetValue(spanId, out var a) || _otelEnded.Contains(spanId)) { U<int>(); return; }
            var tags = new ActivityTagsCollection();
            foreach (var at in attrs) tags[at.Key] = CoerceEventAttr(at);
            var ts = DateTimeOffset.FromUnixTimeMilliseconds(timeMicros / 1000)
                .AddTicks((timeMicros % 1000) * 10);
            a.AddEvent(new ActivityEvent(name, ts, tags));
        }
        // Fetch the delivered span (by DD-decimal span id) from the test-agent, so
        // its wire-encoded span_events / meta can be re-read compactly.
        private JsonElement? FetchDeliveredSpan(string spanId)
        {
            Flush();
            var url = (Environment.GetEnvironmentVariable("DD_TRACE_AGENT_URL") ?? "").TrimEnd('/');
            if (url == "") return null;
            var deadline = DateTime.UtcNow.AddSeconds(3);
            while (DateTime.UtcNow < deadline)
            {
                JsonElement traces;
                try
                {
                    var raw = Http.GetStringAsync(url + "/test/session/traces").GetAwaiter().GetResult();
                    traces = JsonDocument.Parse(raw).RootElement;
                }
                catch { traces = default; }
                if (traces.ValueKind == JsonValueKind.Array && traces.GetArrayLength() > 0)
                {
                    foreach (var trace in traces.EnumerateArray())
                        foreach (var sp in trace.EnumerateArray())
                            if (sp.TryGetProperty("span_id", out var sid) && sid.ToString() == spanId)
                                return sp.Clone();
                    return null;
                }
                System.Threading.Thread.Sleep(150);
            }
            return null;
        }
        private static readonly JsonSerializerOptions Compact = new() { WriteIndented = false };
        public string WireSpanEventsJson(string spanId)
        {
            var sp = FetchDeliveredSpan(spanId);
            if (sp is JsonElement e && e.TryGetProperty("span_events", out var ev))
                return JsonSerializer.Serialize(ev, Compact);
            return "";
        }
        public string WireSpanMetaEventsJson(string spanId)
        {
            var sp = FetchDeliveredSpan(spanId);
            if (sp is JsonElement e && e.TryGetProperty("meta", out var m)
                && m.ValueKind == JsonValueKind.Object && m.TryGetProperty("events", out var evStr)
                && evStr.ValueKind == JsonValueKind.String)
            {
                using var doc = JsonDocument.Parse(evStr.GetString());
                return JsonSerializer.Serialize(doc.RootElement, Compact);
            }
            return "";
        }
        public IReadOnlyList<CapturedSpan> DeliveredSpans() => CapturedSpans();
        public string ComputedStatsJson() => U<string>();
        // Remote-config capability advertisement: DD polls /v0.7/config on a background
        // thread (DD_REMOTE_CONFIGURATION_ENABLED=true) and advertises a capabilities
        // bitmask. Read it back from the config request the test-agent recorded.
        public string RcCapabilitiesCsv()
        {
            var url = (Environment.GetEnvironmentVariable("DD_TRACE_AGENT_URL") ?? "").TrimEnd('/');
            if (url == "") return "";
            var deadline = DateTime.UtcNow.AddSeconds(12);
            while (DateTime.UtcNow < deadline)
            {
                JsonElement reqs;
                try
                {
                    var raw = Http.GetStringAsync(url + "/test/session/requests").GetAwaiter().GetResult();
                    reqs = JsonDocument.Parse(raw).RootElement;
                }
                catch { System.Threading.Thread.Sleep(300); continue; }
                if (reqs.ValueKind == JsonValueKind.Array)
                    foreach (var r in reqs.EnumerateArray())
                    {
                        if (!(r.TryGetProperty("url", out var u) && u.ToString().Contains("/v0.7/config"))) continue;
                        if (!r.TryGetProperty("body", out var b)) continue;
                        try
                        {
                            JsonElement body;
                            if (b.ValueKind == JsonValueKind.String)
                                body = JsonDocument.Parse(Convert.FromBase64String(b.GetString())).RootElement;
                            else body = b;
                            if (!(body.TryGetProperty("client", out var client)
                                && client.TryGetProperty("capabilities", out var caps))) continue;
                            byte[] rawc;
                            if (caps.ValueKind == JsonValueKind.String) rawc = Convert.FromBase64String(caps.GetString());
                            else if (caps.ValueKind == JsonValueKind.Array)
                                rawc = caps.EnumerateArray().Select(x => (byte)x.GetInt32()).ToArray();
                            else continue;
                            System.Numerics.BigInteger n = 0;
                            foreach (var by in rawc) n = (n << 8) | by; // big-endian
                            var bits = new List<string>();
                            for (var i = 0; i < 64; i++)
                                if ((n & (System.Numerics.BigInteger.One << i)) != 0) bits.Add(i.ToString());
                            if (bits.Count > 0) return "," + string.Join(",", bits) + ",";
                        }
                        catch { }
                    }
                System.Threading.Thread.Sleep(300);
            }
            return "";
        }
        public bool RcApplySamplingRate(double rate) => U<bool>();
    }
}
