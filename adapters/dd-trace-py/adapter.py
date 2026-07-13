"""dd-trace-py implementation of the Temper-generated Tracer interface.

Mirrors the dd-trace-js adapter: implements the generated `Tracer` ABC against a
real ddtrace tracer, capturing emitted spans in-memory (read from the span
objects after finish). Span/trace ids are decimal strings (trace id is the low
64 bits, matching the agent payload and the conformance model).
"""
import os
import sys

# The generated library + its Temper runtime live under temper.out/py.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in ("system-tests-redux", "temper-core", "std"):
    sys.path.insert(0, os.path.join(_REPO, "temper.out", "py", _p))

from system_tests_redux.system_tests_redux import (  # noqa: E402
    Tracer, CapturedSpan, CapturedLink, OtelSpanContextInfo, TelemetryConfigItem,
)
import ddtrace  # noqa: E402
from ddtrace.propagation.http import HTTPPropagator  # noqa: E402

_MASK64 = (1 << 64) - 1

# Wire ddtrace's OpenTelemetry bridge once (no-op if unavailable).
_OTEL = None
try:
    from ddtrace.opentelemetry import TracerProvider as _DDTracerProvider
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import SpanKind as _OtelSpanKind
    _otel_trace.set_tracer_provider(_DDTracerProvider())
    _OTEL = _otel_trace.get_tracer("conformance")
    _OTEL_KINDS = {
        "internal": _OtelSpanKind.INTERNAL, "server": _OtelSpanKind.SERVER,
        "client": _OtelSpanKind.CLIENT, "producer": _OtelSpanKind.PRODUCER,
        "consumer": _OtelSpanKind.CONSUMER,
    }
except Exception:
    _OTEL = None


def _low64(trace_id):
    return str(trace_id & _MASK64)


class DdTracePyAdapter(Tracer):
    def __init__(self):
        self._tracer = ddtrace.tracer
        self._by_id = {}     # decimal span id -> span
        self._ctx_by_id = {}  # decimal parent id -> extracted context
        self._otel_by_id = {}  # decimal span id -> otel span
        self._order = []

    def _parent_for(self, parent_id):
        if parent_id == "0" or not parent_id:
            return None
        return self._by_id.get(parent_id) or self._ctx_by_id.get(parent_id)

    def start_span(self, name, parent_id, service="", resource="", span_type=""):
        kwargs = {}
        parent = self._parent_for(parent_id)
        if parent is not None:
            kwargs["child_of"] = parent
        if service:
            kwargs["service"] = service
        if resource:
            kwargs["resource"] = resource
        if span_type:
            kwargs["span_type"] = span_type
        span = self._tracer.start_span(name, **kwargs)
        # ddtrace doesn't auto-copy baggage from a parent/extracted context onto
        # the new span's context; do it so get_baggage works after extraction.
        if parent is not None:
            pctx = parent.context if hasattr(parent, "context") else parent
            pbag = getattr(pctx, "_baggage", None)
            if pbag:
                for k, v in pbag.items():
                    span.context.set_baggage_item(k, v)
        sid = str(span.span_id)
        self._by_id[sid] = span
        self._order.append(span)
        return CapturedSpan(_low64(span.trace_id), sid, parent_id, name,
                            service, resource, span_type, {}, {}, [])

    def finish_span(self, span_id):
        s = self._by_id.get(span_id)
        if s is not None:
            s.finish()

    def set_meta(self, span_id, key, value):
        s = self._by_id.get(span_id)
        if s is not None:
            s.set_tag(key, value)

    def set_metric(self, span_id, key, value):
        s = self._by_id.get(span_id)
        if s is not None:
            s.set_metric(key, value)

    def set_resource(self, span_id, value):
        s = self._by_id.get(span_id)
        if s is not None:
            s.resource = value

    def remove_meta(self, span_id, key):
        s = self._by_id.get(span_id)
        if s is not None:
            s._remove_attribute(key)

    def remove_metric(self, span_id, key):
        s = self._by_id.get(span_id)
        if s is not None:
            s._remove_attribute(key)

    def otel_set_attribute_num(self, span_id, key, value):
        o = self._otel_by_id.get(span_id)
        if o is not None:
            o.set_attribute(key, int(value) if float(value).is_integer() else value)

    def otel_remove_attribute(self, span_id, key):
        # OTel set_attribute(None) stores the string "None" rather than removing,
        # so remove on the underlying span instead -- but only while the span is
        # recording, mirroring OTel set_attribute being a no-op after end.
        o = self._otel_by_id.get(span_id)
        s = self._by_id.get(span_id)
        if o is not None and s is not None and o.is_recording():
            s._remove_attribute(key)

    def set_baggage(self, span_id, key, value):
        s = self._by_id.get(span_id)
        if s is not None:
            s.context.set_baggage_item(key, value)

    def get_baggage(self, span_id, key):
        s = self._by_id.get(span_id)
        if s is None:
            return ""
        return s.context.get_baggage_item(key) or ""

    def get_all_baggage(self, span_id):
        s = self._by_id.get(span_id)
        if s is None:
            return {}
        return dict(getattr(s.context, "_baggage", {}) or {})

    def remove_baggage(self, span_id, key):
        s = self._by_id.get(span_id)
        if s is not None:
            try:
                s.context.remove_baggage_item(key)
            except Exception:
                bag = getattr(s.context, "_baggage", None)
                if bag is not None and key in bag:
                    del bag[key]

    def remove_all_baggage(self, span_id):
        s = self._by_id.get(span_id)
        if s is not None:
            try:
                s.context.remove_all_baggage_items()
            except Exception:
                bag = getattr(s.context, "_baggage", None)
                if bag is not None:
                    bag.clear()

    def add_link(self, span_id, link_to_span_id, attributes):
        span = self._by_id.get(span_id)
        if span is None:
            return
        target = self._by_id.get(link_to_span_id)
        ctx = target.context if target is not None else self._ctx_by_id.get(link_to_span_id)
        if ctx is None:
            return
        span.link_span(ctx, attributes=dict(attributes))

    def extract_headers(self, headers):
        # fold repeated headers with commas (RFC 7230) so duplicate
        # traceparent/tracestate inputs are represented faithfully
        carrier = {}
        for p in headers:
            carrier[p.key] = f"{carrier[p.key]},{p.value}" if p.key in carrier else p.value
        ctx = HTTPPropagator.extract(carrier)
        if ctx is None:
            return "0"
        if ctx.span_id:
            pid = str(ctx.span_id)
            self._ctx_by_id[pid] = ctx
            return pid
        # trace-less context that still carries baggage: keep it so a child span
        # started from it inherits the baggage (baggage-only propagation).
        if getattr(ctx, "_baggage", None):
            self._baggage_ctx_counter = getattr(self, "_baggage_ctx_counter", 0) + 1
            pid = f"bgctx{self._baggage_ctx_counter}"
            self._ctx_by_id[pid] = ctx
            return pid
        return "0"

    def inject_headers(self, span_id):
        span = self._by_id.get(span_id)
        carrier = {}
        if span is not None:
            HTTPPropagator.inject(span, carrier)
        return {k: str(v) for k, v in carrier.items()}

    def flush(self):
        try:
            self._tracer.flush()
        except Exception:
            pass

    def captured_spans(self):
        # A disabled tracer sends nothing to the agent; mirror that here even
        # though we hold the live span objects.
        if not getattr(self._tracer, "enabled", True):
            return []
        out = []
        for span in self._order:
            meta = {k: str(v) for k, v in (span.get_tags() or {}).items()}
            metrics = {}
            for k, v in (span.get_metrics() or {}).items():
                if isinstance(v, (int, float)):
                    metrics[k] = float(v)
            links = []
            try:
                span_links = span._get_links()
            except Exception:
                span_links = []
            for l in (span_links or []):
                attrs = {str(k): str(v) for k, v in (getattr(l, "attributes", {}) or {}).items()}
                # high 64 bits as an unsigned decimal string (a full W3C
                # trace-id-high overflows a 32-bit Temper Int); "0" if absent
                links.append(CapturedLink(str(l.span_id), _low64(l.trace_id), str(l.trace_id >> 64), attrs))
            pid = str(span.parent_id) if span.parent_id else "0"
            out.append(CapturedSpan(
                _low64(span.trace_id), str(span.span_id), pid, span.name,
                span.service or "", span.resource or "", span.span_type or "",
                meta, metrics, links, int(span.error or 0),
            ))
        return out

    def config(self):
        c = ddtrace.config
        def low(v):
            return str(v).lower() if v is not None else "null"
        try:
            agent_url = self._tracer._agent_url
        except Exception:
            agent_url = getattr(c, "_trace_agent_url", None)
        try:
            tags = ",".join(f"{k}:{v}" for k, v in c.tags.items())
        except Exception:
            tags = "null"
        # effective global sample rate = the default-provenance rule's rate
        # (mirrors the reference parametric server's _global_sampling_rate)
        sample_rate = "null"
        try:
            for r in self._tracer._sampler.rules:
                if getattr(r, "provenance", None) == "default":
                    sample_rate = str(r.sample_rate)
                    break
        except Exception:
            pass
        return {
            "dd_service": c.service if c.service is not None else "null",
            "dd_env": c.env if c.env is not None else "null",
            "dd_version": c.version if c.version is not None else "null",
            "dd_trace_agent_url": str(agent_url) if agent_url else "null",
            "dd_trace_rate_limit": str(getattr(c, "_trace_rate_limit", "null")),
            "dd_trace_sample_rate": sample_rate,
            "dd_trace_enabled": low(getattr(c, "_tracing_enabled", True)),
            "dd_trace_propagation_style": ",".join(getattr(c, "_propagation_style_inject", []) or []) or "null",
            "dd_log_level": "null",
            "dd_trace_debug": low(getattr(c, "_debug_mode", False)),
            "dd_runtime_metrics_enabled": low(getattr(c, "_runtime_metrics_enabled", False)),
            "dd_trace_otel_enabled": low(getattr(c, "_otel_enabled", False)),
            "dd_tags": tags,
        }

    # --- test-agent-backed queries (DD_TRACE_AGENT_URL points at ddapm-test-agent) ---
    def _agent_get(self, path):
        import os, urllib.request
        url = os.environ.get("DD_TRACE_AGENT_URL", "").rstrip("/")
        if not url:
            return None
        try:
            return urllib.request.urlopen(url + path, timeout=3).read()
        except Exception:
            return None

    def delivered_spans(self):
        import json, time
        self.flush()
        out = []
        deadline = time.time() + 8
        while time.time() < deadline:
            raw = self._agent_get("/test/session/traces")
            traces = json.loads(raw) if raw else []
            if traces:
                for trace in traces:
                    for sp in trace:
                        meta = {str(k): str(v) for k, v in (sp.get("meta") or {}).items()}
                        metrics = {str(k): float(v) for k, v in (sp.get("metrics") or {}).items()
                                   if isinstance(v, (int, float))}
                        out.append(CapturedSpan(
                            str(sp.get("trace_id")), str(sp.get("span_id")), str(sp.get("parent_id", 0) or 0),
                            sp.get("name", ""), sp.get("service", "") or "", sp.get("resource", "") or "",
                            sp.get("type", "") or "", meta, metrics, [], int(sp.get("error", 0) or 0)))
                break
            time.sleep(0.3)
        return out

    def computed_stats_json(self):
        import json, time
        self.flush()
        deadline = time.time() + 14
        while time.time() < deadline:
            raw = self._agent_get("/test/session/stats")
            stats = json.loads(raw) if raw else []
            if stats:
                return json.dumps(stats, separators=(",", ":"))
            time.sleep(0.5)
        return ""

    def rc_capabilities_csv(self):
        import base64, json, time
        deadline = time.time() + 9
        while time.time() < deadline:
            raw = self._agent_get("/test/session/requests")
            reqs = json.loads(raw) if raw else []
            for r in reqs:
                if "/v0.7/config" not in r.get("url", ""):
                    continue
                b = r.get("body")
                try:
                    body = json.loads(base64.b64decode(b)) if isinstance(b, str) else b
                    caps = body.get("client", {}).get("capabilities")
                    if caps:
                        rawc = base64.b64decode(caps) if isinstance(caps, str) else bytes(caps)
                        n = int.from_bytes(rawc, "big")
                        bits = [str(i) for i in range(64) if n & (1 << i)]
                        if bits:
                            return "," + ",".join(bits) + ","
                except Exception:
                    pass
            time.sleep(0.4)
        return ""

    def rc_apply_sampling_rate(self, rate):
        import os, json, time, base64
        agent = os.environ.get("DD_TRACE_AGENT_URL", "").rstrip("/")
        if not agent:
            return False
        service = os.environ.get("DD_SERVICE", "test_service")
        env = os.environ.get("DD_ENV", "test_env")
        cfg = {
            "action": "enable",
            "service_target": {"service": service, "env": env},
            "lib_config": {"tracing_sampling_rate": rate},
        }
        cid = str(abs(hash(json.dumps(cfg, sort_keys=True))))
        cfg["id"] = cid
        path = f"datadog/2/APM_TRACING/{cid}/config"
        body = json.dumps({"path": path, "msg": cfg}).encode()
        try:
            import urllib.request
            req = urllib.request.Request(agent + "/test/session/responses/config/path",
                                        data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            return False
        # wait for the tracer to poll, apply, and ACK (apply_state == 2) for this config id
        deadline = time.time() + 12
        while time.time() < deadline:
            raw = self._agent_get("/test/session/requests")
            reqs = json.loads(raw) if raw else []
            for r in reqs:
                if "/v0.7/config" not in r.get("url", ""):
                    continue
                b = r.get("body")
                try:
                    payload = json.loads(base64.b64decode(b)) if isinstance(b, str) else b
                    for cs in payload.get("client", {}).get("state", {}).get("config_states", []):
                        if cs.get("id") == cid and cs.get("apply_state") == 2:
                            return True
                except Exception:
                    pass
            time.sleep(0.4)
        return False

    # --- OpenTelemetry span API (via ddtrace's OTel bridge) ---
    def otel_start_span(self, name, parent_id, kind):
        ctx = None
        if parent_id and parent_id != "0":
            parent = self._otel_by_id.get(parent_id)
            if parent is not None:
                ctx = _otel_trace.set_span_in_context(parent)
            else:
                dd_parent = self._by_id.get(parent_id)
                if dd_parent is not None:
                    from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan
                    sc = SpanContext(trace_id=dd_parent.trace_id, span_id=dd_parent.span_id,
                                     is_remote=False, trace_flags=TraceFlags(1))
                    ctx = _otel_trace.set_span_in_context(NonRecordingSpan(sc))
        otel_span = _OTEL.start_span(name, context=ctx, kind=_OTEL_KINDS.get(kind, _OTEL_KINDS["internal"]))
        ddspan = otel_span._ddspan
        sid = str(ddspan.span_id)
        self._by_id[sid] = ddspan        # so captured_spans() includes it
        self._order.append(ddspan)
        self._otel_by_id[sid] = otel_span
        return CapturedSpan(_low64(ddspan.trace_id), sid, parent_id, name, "", "", "", {}, {}, [])

    def otel_set_attribute(self, span_id, key, value):
        s = self._otel_by_id.get(span_id)
        if s is not None:
            s.set_attribute(key, value)

    def _coerce_event_attrs(self, attrs):
        def scalar(kind, v):
            if kind == "int":
                return int(v)
            if kind == "double":
                return float(v)
            if kind == "bool":
                return v == "true"
            return v
        out = {}
        for a in attrs:
            vals = list(a.values)
            if a.kind.endswith("_arr"):
                base = a.kind[:-4]
                out[a.key] = [scalar(base, x) for x in vals]
            else:
                out[a.key] = scalar(a.kind, vals[0] if vals else "")
        return out

    def otel_add_event(self, span_id, name, time_micros, attrs):
        s = self._otel_by_id.get(span_id)
        if s is not None:
            s.add_event(name, attributes=self._coerce_event_attrs(attrs), timestamp=int(time_micros))

    def wire_span_events_json(self, span_id):
        import json as _json
        import msgpack as _msgpack
        from ddtrace.internal.encoding import MsgpackEncoderV04
        dd = self._by_id.get(span_id)
        if dd is None:
            return ""
        enc = MsgpackEncoderV04(8 << 20, 8 << 20)
        enc.put([dd])
        out = enc.encode()
        raw = out[0][0] if isinstance(out, (list, tuple)) else out
        traces = _msgpack.unpackb(raw, raw=False)
        for trace in traces:
            for sp in trace:
                if isinstance(sp, dict) and str(sp.get("span_id")) == span_id:
                    ev = sp.get("span_events")
                    if ev is not None:
                        return _json.dumps(ev, separators=(",", ":"))
        return ""

    def wire_span_meta_events_json(self, span_id):
        import json as _json
        import msgpack as _msgpack
        from ddtrace.internal.encoding import MsgpackEncoderV05
        dd = self._by_id.get(span_id)
        if dd is None:
            return ""
        enc = MsgpackEncoderV05(8 << 20, 8 << 20)
        enc.put([dd])
        out = enc.encode()
        raw = out[0][0] if isinstance(out, (list, tuple)) else out
        dec = _msgpack.unpackb(raw, raw=False, strict_map_key=False)
        strings = dec[0]
        for trace in dec[1]:
            for sp in trace:
                if str(sp[4]) == span_id:
                    meta = {strings[k]: strings[v] for k, v in sp[9].items()}
                    ev = meta.get("events")
                    if ev:
                        return _json.dumps(_json.loads(ev), separators=(",", ":"))
        return ""

    def otel_end_span(self, span_id):
        s = self._otel_by_id.get(span_id)
        if s is not None:
            s.end()

    def otel_is_recording(self, span_id):
        s = self._otel_by_id.get(span_id)
        return bool(s.is_recording()) if s is not None else False

    def otel_span_context(self, span_id):
        s = self._otel_by_id.get(span_id)
        sc = s.get_span_context()
        return OtelSpanContextInfo(format(sc.trace_id, "032x"), format(sc.span_id, "016x"))

    def telemetry_config(self):
        out = []
        try:
            from ddtrace.internal.telemetry import telemetry_writer
            for c in telemetry_writer._report_configurations():
                out.append(TelemetryConfigItem(str(c["name"]), str(c["value"]), str(c["origin"])))
        except Exception:
            pass
        return out

    def otel_set_status(self, span_id, code, description):
        from opentelemetry.trace import StatusCode, Status
        s = self._otel_by_id.get(span_id)
        if s is not None:
            c = getattr(StatusCode, str(code).upper(), StatusCode.UNSET)
            s.set_status(Status(c, description))

    def otel_record_exception(self, span_id, message, attributes):
        s = self._otel_by_id.get(span_id)
        if s is None:
            return
        exc = Exception(message)
        s.record_exception(exc, attributes=dict(attributes) if attributes else None)


def make_adapter():
    return DdTracePyAdapter()
