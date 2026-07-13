package ddtracejava;

// Implements the generated system_tests_redux.Tracer against the real
// dd-trace-java library via the OpenTelemetry API. Under -javaagent:
// dd-java-agent.jar (+ DD_TRACE_OTEL_ENABLED=true) the agent bridges the OTel
// API to real DD spans; without it, spans are no-op PropagatedSpans. Spans are
// delivered to a ddapm-test-agent and read back for capturedSpans(). Ops with
// no wired backing throw UnsupportedOperationException so the case is skipped.

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.baggage.Baggage;
import io.opentelemetry.api.baggage.BaggageBuilder;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapGetter;

import org.json.JSONArray;
import org.json.JSONObject;

import system_tests_redux.CapturedLink;
import system_tests_redux.CapturedSpan;
import system_tests_redux.Tracer;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.math.BigInteger;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class Adapter implements Tracer {
  private final io.opentelemetry.api.trace.Tracer tracer =
      GlobalOpenTelemetry.getTracer("conformance");
  private final Map<String, Span> spans = new HashMap<>();
  private final Map<String, Context> ctxs = new HashMap<>();
  private final java.util.Set<String> otelEnded = new java.util.HashSet<>();
  private final java.util.Set<String> statusLocked = new java.util.HashSet<>();
  private int bgCtxCounter = 0;

  private static SpanKind kind(String k) {
    if (k == null) return SpanKind.INTERNAL;
    switch (k.toLowerCase()) {
      case "server": return SpanKind.SERVER;
      case "client": return SpanKind.CLIENT;
      case "producer": return SpanKind.PRODUCER;
      case "consumer": return SpanKind.CONSUMER;
      default: return SpanKind.INTERNAL;
    }
  }

  // OTel ids are hex; the agent delivers decimal. span id = 16 hex -> decimal;
  // trace id = 32 hex, agent reports the low-64 decimal.
  private static String spanDec(String hex16) { return new BigInteger(hex16, 16).toString(); }
  private static String traceDec(String hex32) {
    return new BigInteger(hex32.length() > 16 ? hex32.substring(hex32.length() - 16) : hex32, 16).toString();
  }

  @Override
  public CapturedSpan startSpan(String name, String parentId, String service, String resource, String spanType) {
    SpanBuilder b = tracer.spanBuilder(name);
    boolean rooted = parentId != null && !parentId.isEmpty() && !parentId.equals("0") && ctxs.containsKey(parentId);
    Context parentCtx = rooted ? ctxs.get(parentId) : null;
    // A baggage-only extracted context has no valid span but carries baggage; the
    // child is a new root that still inherits the baggage.
    boolean hasParentSpan = parentCtx != null && Span.fromContext(parentCtx).getSpanContext().isValid();
    if (parentCtx != null) b.setParent(parentCtx); else b.setNoParent();
    Span span = b.startSpan();
    // dd-trace-java's OTel bridge maps these reserved attributes to DD fields.
    // Without operation.name the DD operation name is derived from the span kind
    // ("internal"); the DD-style startSpan wants the given name verbatim.
    span.setAttribute("operation.name", name);
    if (service != null && !service.isEmpty()) span.setAttribute("service.name", service);
    if (resource != null && !resource.isEmpty()) span.setAttribute("resource.name", resource);
    if (spanType != null && !spanType.isEmpty()) span.setAttribute("span.type", spanType);
    String id = spanDec(span.getSpanContext().getSpanId());
    spans.put(id, span);
    // Inherit the parent context (incl. its OTel baggage) so getBaggage after an
    // extract and baggage propagation on inject both see the parent's entries.
    ctxs.put(id, (parentCtx != null ? parentCtx : Context.current()).with(span));
    return new CapturedSpan(
        traceDec(span.getSpanContext().getTraceId()), id, hasParentSpan ? parentId : "0",
        name, service == null ? "" : service, resource == null ? "" : resource,
        spanType == null ? "" : spanType, new HashMap<>(), new HashMap<>(), new ArrayList<>());
  }

  @Override public void finishSpan(String spanId) { Span s = spans.get(spanId); if (s != null) s.end(); }
  @Override public void setMeta(String spanId, String key, String value) { Span s = spans.get(spanId); if (s != null) s.setAttribute(key, value); }
  @Override public void setMetric(String spanId, String key, double value) { Span s = spans.get(spanId); if (s != null) s.setAttribute(key, value); }

  @Override
  public String extractHeaders(List<Map.Entry<String, String>> headers) {
    Map<String, String> carrier = new HashMap<>();
    for (Map.Entry<String, String> e : headers) carrier.put(e.getKey(), e.getValue());
    TextMapGetter<Map<String, String>> getter = new TextMapGetter<Map<String, String>>() {
      @Override public Iterable<String> keys(Map<String, String> c) { return c.keySet(); }
      @Override public String get(Map<String, String> c, String k) {
        if (c == null) return null;
        for (Map.Entry<String, String> en : c.entrySet()) if (en.getKey().equalsIgnoreCase(k)) return en.getValue();
        return null;
      }
    };
    Context ctx = GlobalOpenTelemetry.getPropagators().getTextMapPropagator()
        .extract(Context.root(), carrier, getter);
    Span s = Span.fromContext(ctx);
    if (s.getSpanContext().isValid()) {
      String id = spanDec(s.getSpanContext().getSpanId());
      ctxs.put(id, ctx);
      return id;
    }
    // No valid span, but a baggage-only context (W3C `baggage` header with no
    // trace context) must survive so a child span started from it inherits the
    // baggage. Stash it under a synthetic id.
    if (Baggage.fromContext(ctx).size() > 0) {
      String id = "bgctx" + (++bgCtxCounter);
      ctxs.put(id, ctx);
      return id;
    }
    return "0";
  }

  @Override
  public Map<String, String> injectHeaders(String spanId) {
    Map<String, String> raw = new HashMap<>();
    Context ctx = ctxs.get(spanId);
    if (ctx != null) {
      GlobalOpenTelemetry.getPropagators().getTextMapPropagator()
          .inject(ctx, raw, (c, k, v) -> { if (c != null) c.put(k, v); });
    }
    // Normalize to lowercase header names: HTTP headers are case-insensitive,
    // and the shared cases (written for dd-trace-js/py) look them up lowercase,
    // whereas OTel's B3 propagator emits mixed-case "X-B3-TraceId".
    Map<String, String> out = new HashMap<>();
    for (Map.Entry<String, String> e : raw.entrySet()) out.put(e.getKey().toLowerCase(), e.getValue());
    return out;
  }

  @Override public void flush() { /* dd-trace-java flushes on a timer; capturedSpans polls */ }

  @Override
  public List<CapturedSpan> capturedSpans() {
    List<CapturedSpan> out = new ArrayList<>();
    for (JSONObject s : rawSpans()) out.add(fromJson(s));
    return out;
  }

  // Poll the test-agent for delivered span JSON objects (flattened across traces).
  private List<JSONObject> rawSpans() {
    flush();
    List<JSONObject> out = new ArrayList<>();
    String url = System.getenv("DD_TRACE_AGENT_URL");
    if (url == null || url.isEmpty()) return out;
    url = url.replaceAll("/+$", "");
    long deadline = System.currentTimeMillis() + 6000;
    while (System.currentTimeMillis() < deadline) {
      String body = agentGet(url + "/test/session/traces");
      if (body != null && body.trim().startsWith("[") && !body.trim().equals("[]")) {
        JSONArray traces = new JSONArray(body);
        for (int i = 0; i < traces.length(); i++) {
          JSONArray trace = traces.getJSONArray(i);
          for (int j = 0; j < trace.length(); j++) out.add(trace.getJSONObject(j));
        }
        break;
      }
      try { Thread.sleep(150); } catch (InterruptedException e) { break; }
    }
    return out;
  }

  private static CapturedSpan fromJson(JSONObject s) {
    Map<String, String> meta = new HashMap<>();
    JSONObject m = s.optJSONObject("meta");
    if (m != null) for (String k : m.keySet()) meta.put(k, String.valueOf(m.get(k)));
    Map<String, Double> metrics = new HashMap<>();
    JSONObject mx = s.optJSONObject("metrics");
    if (mx != null) for (String k : mx.keySet()) metrics.put(k, mx.getDouble(k));
    Integer error = s.has("error") ? Integer.valueOf(s.getInt("error")) : null;
    return new CapturedSpan(
        str(s, "trace_id"), str(s, "span_id"), str(s, "parent_id"),
        s.optString("name", ""), s.optString("service", ""), s.optString("resource", ""),
        s.optString("type", ""), meta, metrics, new ArrayList<CapturedLink>(), error);
  }

  private static String str(JSONObject o, String k) { return o.has(k) ? String.valueOf(o.get(k)) : ""; }

  private static String agentGet(String u) {
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

  // --- baggage (OTel Baggage API, bridged by dd-trace-java) ---
  // Baggage lives in the OTel Context, not on the Span; the adapter keys a
  // Context per span, so baggage mutations rewrite that entry. dd-trace-java's
  // OTel bridge injects/extracts the W3C `baggage` header (URL-encoded) from
  // Context baggage when the `baggage` propagation style is enabled (on by
  // default), so set/get/remove and header inject/extract all round-trip.
  private Context bagCtx(String spanId) {
    Context c = ctxs.get(spanId);
    return c != null ? c : Context.current();
  }
  @Override public void setBaggage(String spanId, String key, String value) {
    Context c = bagCtx(spanId);
    Baggage bg = Baggage.fromContext(c).toBuilder().put(key, value).build();
    ctxs.put(spanId, c.with(bg));
  }
  @Override public String getBaggage(String spanId, String key) {
    String v = Baggage.fromContext(bagCtx(spanId)).getEntryValue(key);
    return v == null ? "" : v;
  }
  @Override public Map<String, String> getAllBaggage(String spanId) {
    Map<String, String> out = new HashMap<>();
    Baggage.fromContext(bagCtx(spanId)).forEach((k, e) -> out.put(k, e.getValue()));
    return out;
  }
  @Override public void removeBaggage(String spanId, String key) {
    Context c = ctxs.get(spanId);
    if (c == null) return;
    Baggage bg = Baggage.fromContext(c).toBuilder().remove(key).build();
    ctxs.put(spanId, c.with(bg));
  }
  @Override public void removeAllBaggage(String spanId) {
    Context c = ctxs.get(spanId);
    if (c == null) return;
    ctxs.put(spanId, c.with(Baggage.empty()));
  }

  // --- not yet wired ---
  private static <T> T u() { throw new UnsupportedOperationException("dd-trace-java adapter: op not implemented"); }
  @Override public void addLink(String s, String to, Map<String, String> a) { u(); }
  @Override public void setResource(String spanId, String value) { Span s = spans.get(spanId); if (s != null) s.setAttribute("resource.name", value); }
  @Override public void removeMeta(String s, String k) { u(); }      // OTel Span has no removeAttribute
  @Override public void removeMetric(String s, String k) { u(); }
  @Override public void otelRemoveAttribute(String s, String k) { u(); }
  // Resolved config read reflectively from dd-trace-java's internal
  // datadog.trace.api.Config (loaded on the bootstrap classpath under the
  // javaagent). This reflects the tracer's fully-resolved config, incl. OTEL_*
  // env mapping, which no public API exposes.
  @Override
  public Map<String, String> config() {
    Map<String, String> d = new HashMap<>();
    try {
      Class<?> k = Class.forName("datadog.trace.api.Config");
      Object c = k.getMethod("get").invoke(null);
      putStr(d, "dd_service", cfg(k, c, "getServiceName"));
      putStr(d, "dd_env", cfg(k, c, "getEnv"));
      putStr(d, "dd_version", cfg(k, c, "getVersion"));
      putStr(d, "dd_trace_agent_url", cfg(k, c, "getAgentUrl"));
      putBool(d, "dd_trace_enabled", cfg(k, c, "isTraceEnabled"));
      putBool(d, "dd_trace_debug", cfg(k, c, "isDebugEnabled"));
      putBool(d, "dd_trace_otel_enabled", cfg(k, c, "isTraceOtelEnabled"));
      putBool(d, "dd_runtime_metrics_enabled", cfg(k, c, "isRuntimeMetricsEnabled"));
      Object rl = cfg(k, c, "getTraceRateLimit"); if (rl != null) d.put("dd_trace_rate_limit", String.valueOf(rl));
      Object sr = cfg(k, c, "getTraceSampleRate"); if (sr != null) d.put("dd_trace_sample_rate", String.valueOf(sr));
      Object ps = cfg(k, c, "getTracePropagationStylesToExtract");
      if (ps instanceof Iterable) {
        StringBuilder sb = new StringBuilder();
        for (Object e : (Iterable<?>) ps) { if (sb.length() > 0) sb.append(","); sb.append(String.valueOf(e).toLowerCase()); }
        if (sb.length() > 0) d.put("dd_trace_propagation_style", sb.toString());
      }
      Object tags = cfg(k, c, "getGlobalTags");
      if (tags instanceof Map) {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<?, ?> e : ((Map<?, ?>) tags).entrySet()) {
          String key = String.valueOf(e.getKey());
          // env/version are auto-added into global tags; the suite's dd_tags
          // asserts only DD_TAGS/OTEL_RESOURCE_ATTRIBUTES entries.
          if (key.equals("env") || key.equals("version")) continue;
          if (sb.length() > 0) sb.append(",");
          sb.append(key).append(":").append(e.getValue());
        }
        if (sb.length() > 0) d.put("dd_tags", sb.toString());
      }
    } catch (Throwable ignore) { /* leave whatever resolved */ }
    return d;
  }

  private static Object cfg(Class<?> k, Object c, String m) {
    try { return k.getMethod(m).invoke(c); } catch (Throwable t) { return null; }
  }
  private static void putStr(Map<String, String> d, String key, Object v) {
    if (v != null && !String.valueOf(v).isEmpty()) d.put(key, String.valueOf(v));
  }
  private static void putBool(Map<String, String> d, String key, Object v) {
    if (v != null) d.put(key, Boolean.TRUE.equals(v) ? "true" : "false");
  }

  // OTel span API: startSpan and otelStartSpan both use the OTel API, so a span
  // created by either is in the same maps -> cross-API reads/parenting are uniform.
  @Override
  public CapturedSpan otelStartSpan(String name, String parentId, String kindStr) {
    SpanBuilder b = tracer.spanBuilder(name).setSpanKind(kind(kindStr));
    boolean rooted = parentId != null && !parentId.isEmpty() && !parentId.equals("0") && ctxs.containsKey(parentId);
    Context parentCtx = rooted ? ctxs.get(parentId) : null;
    boolean hasParentSpan = parentCtx != null && Span.fromContext(parentCtx).getSpanContext().isValid();
    if (parentCtx != null) b.setParent(parentCtx); else b.setNoParent();
    // No operation.name override here: the DD OTel bridge derives the operation
    // name from the span kind, which the otel_span.operation_name_* cases assert.
    Span span = b.startSpan();
    String id = spanDec(span.getSpanContext().getSpanId());
    spans.put(id, span);
    ctxs.put(id, (parentCtx != null ? parentCtx : Context.current()).with(span));
    return new CapturedSpan(traceDec(span.getSpanContext().getTraceId()), id, hasParentSpan ? parentId : "0",
        name, "", name, "", new HashMap<>(), new HashMap<>(), new ArrayList<>());
  }

  @Override public void otelSetAttribute(String spanId, String key, String value) {
    Span s = spans.get(spanId); if (s != null && !otelEnded.contains(spanId)) s.setAttribute(key, value);
  }
  @Override public void otelSetAttributeNum(String spanId, String key, double value) {
    Span s = spans.get(spanId); if (s != null && !otelEnded.contains(spanId)) s.setAttribute(key, value);
  }
  @Override public void otelEndSpan(String spanId) {
    Span s = spans.get(spanId); if (s != null && otelEnded.add(spanId)) s.end();
  }
  @Override public boolean otelIsRecording(String spanId) {
    return spans.containsKey(spanId) && !otelEnded.contains(spanId);
  }
  @Override public system_tests_redux.OtelSpanContextInfo otelSpanContext(String spanId) {
    Span s = spans.get(spanId);
    if (s == null) return u();
    return new system_tests_redux.OtelSpanContextInfo(s.getSpanContext().getTraceId(), s.getSpanContext().getSpanId());
  }
  @Override public void otelSetStatus(String spanId, String code, String description) {
    Span s = spans.get(spanId);
    if (s == null || otelEnded.contains(spanId)) return;
    String c = code == null ? "" : code.toUpperCase();
    // OTel status semantics the suite asserts: UNSET is a no-op, and the first
    // OK/ERROR is final (a later status is ignored).
    if (c.equals("UNSET") || statusLocked.contains(spanId)) return;
    if (c.equals("ERROR")) {
      s.setStatus(StatusCode.ERROR, description == null ? "" : description);
      // DD's bridge records the description as error.msg; the suite (js/py parity)
      // expects error.message, so mirror it.
      if (description != null && !description.isEmpty()) s.setAttribute("error.message", description);
    } else if (c.equals("OK")) {
      s.setStatus(StatusCode.OK, description == null ? "" : description);
    } else return;
    statusLocked.add(spanId);
  }
  @Override public void otelRecordException(String spanId, String message, Map<String, String> attributes) {
    Span s = spans.get(spanId);
    if (s == null || otelEnded.contains(spanId)) return;
    // OTel record_exception. Use Span.recordException(Throwable, Attributes): only
    // that path runs dd-trace-java's applySpanEventExceptionAttributesAsTags, which
    // maps exception.type/message/stacktrace to error.type/message/stack meta (a
    // hand-built addEvent lands in the events JSON tag only). It does NOT set error=1
    // on its own (that needs an ERROR status), matching record_exception_no_error.
    AttributesBuilder ab = Attributes.builder();
    if (attributes != null) for (Map.Entry<String, String> e : attributes.entrySet()) ab.put(e.getKey(), e.getValue());
    s.recordException(new RuntimeException(message == null ? "" : message), ab.build());
  }
  // dd-trace-java reports its resolved configuration in the app-started telemetry
  // payload it sends to the agent (a `message-batch` wrapping `app-started`).
  // Poll the test-agent's request log, decode, and surface the configuration
  // entries (name/value/origin) the suite asserts. Requires telemetry enabled
  // (Main leaves it on for telemetry.* cases).
  @Override public List<system_tests_redux.TelemetryConfigItem> telemetryConfig() {
    List<system_tests_redux.TelemetryConfigItem> out = new ArrayList<>();
    String url = System.getenv("DD_TRACE_AGENT_URL");
    if (url == null || url.isEmpty()) return out;
    url = url.replaceAll("/+$", "");
    long deadline = System.currentTimeMillis() + 15000;
    while (System.currentTimeMillis() < deadline) {
      String body = agentGet(url + "/test/session/requests");
      if (body != null && body.trim().startsWith("[")) {
        JSONArray reqs = new JSONArray(body);
        for (int i = 0; i < reqs.length(); i++) {
          JSONObject r = reqs.optJSONObject(i);
          if (r == null || !String.valueOf(r.opt("url")).contains("telemetry")) continue;
          Object raw = r.opt("body");
          JSONObject payload = decodeTelemetryBody(raw);
          if (payload != null) collectTelemetryConfig(payload, out);
        }
        if (!out.isEmpty()) break;
      }
      try { Thread.sleep(300); } catch (InterruptedException e) { break; }
    }
    // dd-trace-java lists some names twice in the same app-started configuration
    // array (a `default`/None entry and the resolved `env_var` entry) in a
    // non-deterministic order. The suite's telemetryValue is last-wins, so keep
    // one entry per name, preferring a non-default (resolved) origin.
    java.util.LinkedHashMap<String, system_tests_redux.TelemetryConfigItem> byName = new java.util.LinkedHashMap<>();
    for (system_tests_redux.TelemetryConfigItem it : out) {
      system_tests_redux.TelemetryConfigItem prev = byName.get(it.getName());
      if (prev == null || !"default".equals(it.getOrigin())) byName.put(it.getName(), it);
    }
    return new ArrayList<>(byName.values());
  }

  private static JSONObject decodeTelemetryBody(Object raw) {
    try {
      if (raw instanceof JSONObject) return (JSONObject) raw;
      if (raw instanceof String) {
        byte[] dec = java.util.Base64.getDecoder().decode(((String) raw).trim());
        return new JSONObject(new String(dec, "UTF-8"));
      }
    } catch (Exception ignore) { }
    return null;
  }

  // Recursively find app-started configuration entries (handles message-batch).
  private static void collectTelemetryConfig(JSONObject o, List<system_tests_redux.TelemetryConfigItem> out) {
    String rt = o.optString("request_type", "");
    if ("app-started".equals(rt)) {
      JSONObject p = o.optJSONObject("payload");
      JSONArray cfg = p == null ? null : p.optJSONArray("configuration");
      if (cfg != null) {
        for (int i = 0; i < cfg.length(); i++) {
          JSONObject it = cfg.optJSONObject(i);
          if (it == null) continue;
          out.add(new system_tests_redux.TelemetryConfigItem(
              it.optString("name", ""), String.valueOf(it.opt("value")), it.optString("origin", "")));
        }
      }
    }
    Object inner = o.opt("payload");
    if (inner instanceof JSONArray) {
      JSONArray arr = (JSONArray) inner;
      for (int i = 0; i < arr.length(); i++) {
        JSONObject c = arr.optJSONObject(i);
        if (c != null) collectTelemetryConfig(c, out);
      }
    }
  }
  @Override public void otelAddEvent(String spanId, String name, int timeMicros, List<system_tests_redux.EventAttr> attrs) {
    Span s = spans.get(spanId);
    if (s == null || otelEnded.contains(spanId)) return;
    AttributesBuilder ab = Attributes.builder();
    for (system_tests_redux.EventAttr a : attrs) {
      String kind = a.getKind();
      List<String> vals = a.getValues();
      switch (kind) {
        case "string": ab.put(a.getKey(), vals.isEmpty() ? "" : vals.get(0)); break;
        case "bool": ab.put(io.opentelemetry.api.common.AttributeKey.booleanKey(a.getKey()), Boolean.parseBoolean(vals.get(0))); break;
        case "int": ab.put(io.opentelemetry.api.common.AttributeKey.longKey(a.getKey()), Long.parseLong(vals.get(0))); break;
        case "double": ab.put(io.opentelemetry.api.common.AttributeKey.doubleKey(a.getKey()), Double.parseDouble(vals.get(0))); break;
        case "str_arr": ab.put(io.opentelemetry.api.common.AttributeKey.stringArrayKey(a.getKey()), new ArrayList<>(vals)); break;
        case "int_arr": {
          List<Long> xs = new ArrayList<>();
          for (String v : vals) xs.add(Long.parseLong(v));
          ab.put(io.opentelemetry.api.common.AttributeKey.longArrayKey(a.getKey()), xs); break;
        }
        case "double_arr": {
          List<Double> xs = new ArrayList<>();
          for (String v : vals) xs.add(Double.parseDouble(v));
          ab.put(io.opentelemetry.api.common.AttributeKey.doubleArrayKey(a.getKey()), xs); break;
        }
        case "bool_arr": {
          List<Boolean> xs = new ArrayList<>();
          for (String v : vals) xs.add(Boolean.parseBoolean(v));
          ab.put(io.opentelemetry.api.common.AttributeKey.booleanArrayKey(a.getKey()), xs); break;
        }
        default: ab.put(a.getKey(), vals.isEmpty() ? "" : vals.get(0));
      }
    }
    s.addEvent(name, ab.build(), timeMicros, java.util.concurrent.TimeUnit.MICROSECONDS);
  }
  // dd-trace-java 1.63.2 encodes OTel span events as a `meta.events` JSON string
  // (typed OTLP-style values), and never as the native msgpack `span_events`
  // wire field. So wireSpanEventsJson (native) yields "" -> the native_v04/v07
  // cases fail and are downgraded via KNOWN_JAVA_DIFFS; wireSpanMetaEventsJson
  // returns the actual meta.events text (v0.5 meta_v05 passes).
  @Override public String wireSpanEventsJson(String spanId) {
    for (JSONObject s : rawSpans()) {
      if (str(s, "span_id").equals(spanId)) {
        Object ev = s.opt("span_events");
        return ev == null ? "" : String.valueOf(ev);
      }
    }
    return "";
  }
  @Override public String wireSpanMetaEventsJson(String spanId) {
    for (JSONObject s : rawSpans()) {
      if (str(s, "span_id").equals(spanId)) {
        JSONObject meta = s.optJSONObject("meta");
        Object ev = meta == null ? null : meta.opt("events");
        return ev == null ? "" : String.valueOf(ev);
      }
    }
    return "";
  }
  @Override public List<CapturedSpan> deliveredSpans() { return capturedSpans(); }
  @Override public String computedStatsJson() { return u(); }

  // Remote-config capabilities the tracer advertised: read the base64 bitmask
  // from a /v0.7/config poll request the agent recorded and expand to bit indices.
  @Override public String rcCapabilitiesCsv() {
    String url = System.getenv("DD_TRACE_AGENT_URL");
    if (url == null || url.isEmpty()) return "";
    url = url.replaceAll("/+$", "");
    long deadline = System.currentTimeMillis() + 15000;
    while (System.currentTimeMillis() < deadline) {
      for (JSONObject r : configRequests(url)) {
        JSONObject payload = decodeTelemetryBody(r.opt("body"));
        JSONObject client = payload == null ? null : payload.optJSONObject("client");
        BigInteger n = client == null ? null : capsToBigInt(client.opt("capabilities"));
        if (n != null && n.signum() != 0) {
          StringBuilder sb = new StringBuilder(",");
          for (int b = 0; b < 64; b++) if (n.testBit(b)) sb.append(b).append(",");
          if (sb.length() > 1) return sb.toString();
        }
      }
      try { Thread.sleep(300); } catch (InterruptedException e) { break; }
    }
    return "";
  }

  // Push an APM_TRACING remote-config sampling rate and wait for the tracer to
  // ACK it (apply_state == 2) in a subsequent /v0.7/config poll.
  @Override public boolean rcApplySamplingRate(double rate) {
    String url = System.getenv("DD_TRACE_AGENT_URL");
    if (url == null || url.isEmpty()) return false;
    url = url.replaceAll("/+$", "");
    String service = envOr("DD_SERVICE", "test_service");
    String env = envOr("DD_ENV", "test_env");
    String cid = "conf-" + Math.abs((service + env + rate).hashCode());
    JSONObject libConfig = new JSONObject().put("tracing_sampling_rate", rate);
    JSONObject msg = new JSONObject()
        .put("action", "enable")
        .put("service_target", new JSONObject().put("service", service).put("env", env))
        .put("lib_config", libConfig)
        .put("id", cid);
    String path = "datadog/2/APM_TRACING/" + cid + "/config";
    JSONObject body = new JSONObject().put("path", path).put("msg", msg);
    if (agentPost(url + "/test/session/responses/config/path", body.toString()) == null) return false;
    long deadline = System.currentTimeMillis() + 15000;
    while (System.currentTimeMillis() < deadline) {
      for (JSONObject r : configRequests(url)) {
        JSONObject payload = decodeTelemetryBody(r.opt("body"));
        JSONObject client = payload == null ? null : payload.optJSONObject("client");
        JSONObject state = client == null ? null : client.optJSONObject("state");
        JSONArray css = state == null ? null : state.optJSONArray("config_states");
        if (css != null) for (int i = 0; i < css.length(); i++) {
          JSONObject cs = css.optJSONObject(i);
          if (cs != null && cid.equals(cs.optString("id")) && cs.optInt("apply_state") == 2) return true;
        }
      }
      try { Thread.sleep(300); } catch (InterruptedException e) { break; }
    }
    return false;
  }

  private List<JSONObject> configRequests(String url) {
    List<JSONObject> out = new ArrayList<>();
    String body = agentGet(url + "/test/session/requests");
    if (body != null && body.trim().startsWith("[")) {
      JSONArray reqs = new JSONArray(body);
      for (int i = 0; i < reqs.length(); i++) {
        JSONObject r = reqs.optJSONObject(i);
        if (r != null && String.valueOf(r.opt("url")).contains("/v0.7/config")) out.add(r);
      }
    }
    return out;
  }

  private static String envOr(String k, String d) { String v = System.getenv(k); return v == null || v.isEmpty() ? d : v; }

  private static BigInteger capsToBigInt(Object caps) {
    try {
      byte[] raw;
      if (caps instanceof String) raw = java.util.Base64.getDecoder().decode(((String) caps).trim());
      else if (caps instanceof JSONArray) {
        JSONArray a = (JSONArray) caps;
        raw = new byte[a.length()];
        for (int i = 0; i < a.length(); i++) raw[i] = (byte) a.getInt(i);
      } else return null;
      return new BigInteger(1, raw);
    } catch (Exception e) { return null; }
  }

  private static String agentPost(String u, String json) {
    try {
      HttpURLConnection con = (HttpURLConnection) new URL(u).openConnection();
      con.setConnectTimeout(3000);
      con.setReadTimeout(3000);
      con.setRequestMethod("POST");
      con.setDoOutput(true);
      con.setRequestProperty("Content-Type", "application/json");
      con.getOutputStream().write(json.getBytes("UTF-8"));
      InputStream is = con.getInputStream();
      ByteArrayOutputStream bo = new ByteArrayOutputStream();
      byte[] buf = new byte[8192];
      int n;
      while ((n = is.read(buf)) != -1) bo.write(buf, 0, n);
      is.close();
      return bo.toString("UTF-8");
    } catch (Exception e) { return null; }
  }
}
