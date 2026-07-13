"""Native dd-trace-go adapter, driven by the Temper suite compiled to Python.

The Go tracer is exposed to C (`go build -buildmode=c-shared` -> libddtracego.dylib)
and called in-process via ctypes FFI — no RPC, no subprocess-server. This class
implements the generated Python `Tracer` ABC; unimplemented ops raise
NotImplementedError so the runner records the case as skipped. Spans are
delivered to a real ddapm-test-agent (DD_TRACE_AGENT_URL) and read back for
captured_spans().
"""
import ctypes
import json
import os
import time
import urllib.request

from system_tests_redux.system_tests_redux import (  # noqa: E402
    Tracer, CapturedSpan, OtelSpanContextInfo, TelemetryConfigItem,
)

HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = None


def _load():
    global _LIB
    if _LIB is not None:
        return _LIB
    lib = ctypes.CDLL(os.path.join(HERE, "libddtracego.dylib"))
    cp = ctypes.c_char_p
    vp = ctypes.c_void_p
    lib.ddgo_init.argtypes = []
    lib.ddgo_stop.argtypes = []
    lib.ddgo_start_span.restype = vp
    lib.ddgo_start_span.argtypes = [cp, cp, cp, cp, cp]
    lib.ddgo_finish_span.argtypes = [cp]
    lib.ddgo_set_meta.argtypes = [cp, cp, cp]
    lib.ddgo_set_metric.argtypes = [cp, cp, ctypes.c_double]
    lib.ddgo_extract.restype = vp
    lib.ddgo_extract.argtypes = [cp]
    lib.ddgo_inject.restype = vp
    lib.ddgo_inject.argtypes = [cp]
    lib.ddgo_flush.argtypes = []
    lib.ddgo_free.argtypes = [vp]
    lib.ddgo_otel_start_span.restype = vp
    lib.ddgo_otel_start_span.argtypes = [cp, cp, cp]
    lib.ddgo_otel_set_attr.argtypes = [cp, cp, cp]
    lib.ddgo_otel_set_attr_num.argtypes = [cp, cp, ctypes.c_double]
    lib.ddgo_otel_end.argtypes = [cp]
    lib.ddgo_otel_is_recording.restype = ctypes.c_int
    lib.ddgo_otel_is_recording.argtypes = [cp]
    lib.ddgo_otel_span_context.restype = vp
    lib.ddgo_otel_span_context.argtypes = [cp]
    lib.ddgo_otel_set_status.argtypes = [cp, cp, cp]
    lib.ddgo_otel_add_event.argtypes = [cp, cp, ctypes.c_longlong, cp]
    lib.ddgo_wire_span_events_json.restype = vp
    lib.ddgo_wire_span_events_json.argtypes = [cp]
    lib.ddgo_wire_span_meta_events_json.restype = vp
    lib.ddgo_wire_span_meta_events_json.argtypes = [cp]
    lib.ddgo_config.restype = vp
    lib.ddgo_config.argtypes = []
    lib.ddgo_set_resource.argtypes = [cp, cp]
    lib.ddgo_set_baggage.argtypes = [cp, cp, cp]
    lib.ddgo_get_baggage.restype = vp
    lib.ddgo_get_baggage.argtypes = [cp, cp]
    lib.ddgo_get_all_baggage.restype = vp
    lib.ddgo_get_all_baggage.argtypes = [cp]
    lib.ddgo_init()
    _LIB = lib
    return lib


def _take(lib, ptr):
    """Copy a Go-allocated C string into Python and free it."""
    if not ptr:
        return ""
    s = ctypes.cast(ptr, ctypes.c_char_p).value or b""
    lib.ddgo_free(ptr)
    return s.decode("utf-8", "replace")


def _b(s):
    return str(s).encode("utf-8")


class DdTraceGoAdapter(Tracer):
    def __init__(self):
        self._lib = _load()

    # --- core span ops (FFI into dd-trace-go) ---
    def start_span(self, name, parent_id, service="", resource="", span_type=""):
        out = _take(self._lib, self._lib.ddgo_start_span(
            _b(name), _b(parent_id), _b(service), _b(resource), _b(span_type)))
        span_id, _, trace_id = out.partition(",")
        return CapturedSpan(trace_id, span_id, parent_id or "0",
                            name, service, resource, span_type, {}, {}, [])

    def finish_span(self, span_id):
        self._lib.ddgo_finish_span(_b(span_id))

    def set_meta(self, span_id, key, value):
        self._lib.ddgo_set_meta(_b(span_id), _b(key), _b(value))

    def set_metric(self, span_id, key, value):
        self._lib.ddgo_set_metric(_b(span_id), _b(key), ctypes.c_double(float(value)))

    def extract_headers(self, headers):
        payload = json.dumps([[p.key, p.value] for p in headers])
        return _take(self._lib, self._lib.ddgo_extract(_b(payload)))

    def inject_headers(self, span_id):
        raw = _take(self._lib, self._lib.ddgo_inject(_b(span_id)))
        try:
            return dict(json.loads(raw))
        except Exception:
            return {}

    def flush(self):
        self._lib.ddgo_flush()

    def captured_spans(self):
        # spans were delivered to the real test-agent; read them back
        self.flush()
        url = os.environ.get("DD_TRACE_AGENT_URL", "").rstrip("/")
        if not url:
            return []
        out = []
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                raw = urllib.request.urlopen(url + "/test/session/traces", timeout=3).read()
                traces = json.loads(raw)
            except Exception:
                traces = []
            if traces:
                for trace in traces:
                    for sp in trace:
                        meta = {str(k): str(v) for k, v in (sp.get("meta") or {}).items()}
                        metrics = {str(k): float(v) for k, v in (sp.get("metrics") or {}).items()
                                   if isinstance(v, (int, float))}
                        out.append(CapturedSpan(
                            str(sp.get("trace_id")), str(sp.get("span_id")),
                            str(sp.get("parent_id", 0) or 0), sp.get("name", ""),
                            sp.get("service", "") or "", sp.get("resource", "") or "",
                            sp.get("type", "") or "", meta, metrics, [], int(sp.get("error", 0) or 0)))
                break
            time.sleep(0.3)
        return out

    # --- OpenTelemetry span API (via dd-trace-go's OTel bridge) ---
    def otel_start_span(self, name, parent_id, kind):
        out = _take(self._lib, self._lib.ddgo_otel_start_span(_b(name), _b(parent_id), _b(kind)))
        span_id, _, trace_id = out.partition(",")
        return CapturedSpan(trace_id, span_id, parent_id or "0", name, "", "", "", {}, {}, [])

    def otel_set_attribute(self, span_id, key, value):
        self._lib.ddgo_otel_set_attr(_b(span_id), _b(key), _b(value))

    def otel_set_attribute_num(self, span_id, key, value):
        self._lib.ddgo_otel_set_attr_num(_b(span_id), _b(key), ctypes.c_double(float(value)))

    def otel_end_span(self, span_id):
        self._lib.ddgo_otel_end(_b(span_id))

    def otel_is_recording(self, span_id):
        return bool(self._lib.ddgo_otel_is_recording(_b(span_id)))

    def otel_span_context(self, span_id):
        out = _take(self._lib, self._lib.ddgo_otel_span_context(_b(span_id)))
        trace_id, _, span = out.partition(",")
        return OtelSpanContextInfo(trace_id, span)

    def otel_set_status(self, span_id, code, description):
        self._lib.ddgo_otel_set_status(_b(span_id), _b(code), _b(description))

    def delivered_spans(self):
        # same wire source as captured_spans (spans the tracer sent to the agent)
        return self.captured_spans()

    def config(self):
        raw = _take(self._lib, self._lib.ddgo_config())
        try:
            return dict(json.loads(raw))
        except Exception:
            return {}

    def set_resource(self, span_id, value):
        self._lib.ddgo_set_resource(_b(span_id), _b(value))

    def set_baggage(self, span_id, key, value):
        self._lib.ddgo_set_baggage(_b(span_id), _b(key), _b(value))

    def get_baggage(self, span_id, key):
        return _take(self._lib, self._lib.ddgo_get_baggage(_b(span_id), _b(key)))

    def get_all_baggage(self, span_id):
        raw = _take(self._lib, self._lib.ddgo_get_all_baggage(_b(span_id)))
        try:
            return dict(json.loads(raw))
        except Exception:
            return {}

    def computed_stats_json(self):
        self.flush()
        url = os.environ.get("DD_TRACE_AGENT_URL", "").rstrip("/")
        if not url:
            return ""
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                raw = urllib.request.urlopen(url + "/test/session/stats", timeout=3).read()
                stats = json.loads(raw)
            except Exception:
                stats = []
            if stats:
                return json.dumps(stats, separators=(",", ":"))
            time.sleep(0.4)
        return ""

    # --- not yet exposed through the c-shared surface ---
    def _u(self, *a, **k):
        raise NotImplementedError("dd-trace-go adapter: op not implemented")

    # --- OpenTelemetry span events (via dd-trace-go's OTel bridge + wire encoder) ---
    def otel_add_event(self, span_id, name, time_micros, attrs):
        payload = json.dumps([
            {"key": a.key, "kind": a.kind, "values": list(a.values)} for a in attrs
        ])
        self._lib.ddgo_otel_add_event(_b(span_id), _b(name),
                                      ctypes.c_longlong(int(time_micros)), _b(payload))

    def wire_span_events_json(self, span_id):
        return _take(self._lib, self._lib.ddgo_wire_span_events_json(_b(span_id)))

    def wire_span_meta_events_json(self, span_id):
        return _take(self._lib, self._lib.ddgo_wire_span_meta_events_json(_b(span_id)))

    # --- app-started telemetry config (read back from the test-agent) ---
    # dd-trace-go emits its resolved config in the app-started telemetry event.
    # It sends both short internal names (service/env/version/trace_header_tags,
    # origin "default") and, for env-driven values, the canonical DD_* names
    # with origin "env_var". The suite keys config by the canonical DD_* name, so
    # we normalize: dedupe per name keeping the highest-provenance origin, and
    # alias the few short names go doesn't also emit under a DD_* name
    # (trace_header_tags -> DD_TRACE_HEADER_TAGS). Values/origins are exactly what
    # the library reported; only the label is normalized (same pattern as config()).
    _TELEMETRY_ALIASES = {"trace_header_tags": "DD_TRACE_HEADER_TAGS"}
    _ORIGIN_RANK = {"env_var": 4, "remote_config": 3, "code": 2, "calculated": 1,
                    "default": 0, "": 0}

    def telemetry_config(self):
        url = os.environ.get("DD_TRACE_AGENT_URL", "").rstrip("/")
        if not url:
            return []
        configs = None
        deadline = time.time() + 10
        while time.time() < deadline and not configs:
            try:
                raw = urllib.request.urlopen(url + "/test/session/apmtelemetry", timeout=3).read()
                events = json.loads(raw)
            except Exception:
                events = []
            for e in events:
                if e.get("request_type") != "app-started":
                    continue
                c = (e.get("payload") or {}).get("configuration")
                if c:
                    configs = c
                    break
            if not configs:
                time.sleep(0.4)
        if not configs:
            return []
        # Dedupe per canonical name, keeping the highest-provenance entry (so an
        # env_var override wins over a same-name default placeholder go also emits).
        best = {}

        def consider(name, value, origin):
            rank = self._ORIGIN_RANK.get(origin, 0)
            prev = best.get(name)
            if prev is None or rank > prev[0]:
                best[name] = (rank, str(value), origin)

        for c in configs:
            name = str(c.get("name", ""))
            value = c.get("value", "")
            origin = str(c.get("origin", "") or "")
            consider(name, value, origin)
            alias = self._TELEMETRY_ALIASES.get(name)
            if alias:
                consider(alias, value, origin)
        return [TelemetryConfigItem(n, v, o) for n, (_r, v, o) in best.items()]

    # --- remote config (agent-backed; the c-shared RC poller drives /v0.7/config) ---
    def _agent_url(self):
        return os.environ.get("DD_TRACE_AGENT_URL", "").rstrip("/")

    def _agent_get(self, path):
        url = self._agent_url()
        if not url:
            return None
        try:
            return urllib.request.urlopen(url + path, timeout=3).read()
        except Exception:
            return None

    def rc_capabilities_csv(self):
        import base64
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
        import base64
        agent = self._agent_url()
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
            req = urllib.request.Request(agent + "/test/session/responses/config/path",
                                         data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            return False
        # wait for the tracer to poll, apply, and ACK (apply_state == 2) this config id
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

    # --- not yet exposed through the c-shared surface ---
    add_link = _u
    remove_meta = _u
    remove_metric = _u
    remove_baggage = _u
    remove_all_baggage = _u
    otel_remove_attribute = _u
    otel_record_exception = _u


def make_adapter():
    return DdTraceGoAdapter()
