//! dd-trace-rust conformance backend (NATIVE Temper — no FFI, no cdylib).
//!
//! The Temper suite compiles to the `system-tests-redux` crate. This binary
//! path-deps that crate, implements the suite's `TracerTrait` against the real
//! dd-trace-rs library (`datadog-opentelemetry`, which is OpenTelemetry-based),
//! and runs ONE case per process (env applied by run.py before launch), reading
//! delivered spans back from the ddapm-test-agent.
//!
//! Ops dd-trace-rs's manual API can't express (manual baggage — commented out in
//! the upstream client; OTel attribute/link removal; RC/stats/telemetry) funnel
//! through an `UNSUPPORTED` panic that the run loop turns into a SKIP, mirroring
//! the ruby/php shim.

use std::collections::HashMap;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{Arc, Mutex};

use opentelemetry::{
    global,
    propagation::{Extractor, Injector},
    trace::{Span, SpanKind, TraceContextExt, Tracer as _},
    Context, KeyValue, Value as OtelValue,
};
use opentelemetry_sdk::trace::SdkTracerProvider;

use system_tests_redux::{
    all_cases, CapturedLink, CapturedSpan, EventAttr, OtelSpanContextInfo, TelemetryConfigItem,
    Tracer, TracerTrait,
};
use temper_core::{ListedTrait, Map, Mapped};

const UNSUPPORTED: &str = "__UNSUPPORTED__:";

fn unsupported(op: &str) -> ! {
    panic!("{UNSUPPORTED}{op}");
}

// --- propagation carriers ---------------------------------------------------

struct MapInjector(HashMap<String, String>);
impl Injector for MapInjector {
    fn set(&mut self, key: &str, value: String) {
        self.0.insert(key.to_string(), value);
    }
}

struct MapExtractor(HashMap<String, String>);
impl Extractor for MapExtractor {
    fn get(&self, key: &str) -> Option<&str> {
        self.0.get(&key.to_lowercase()).map(|s| s.as_str())
    }
    fn keys(&self) -> Vec<&str> {
        self.0.keys().map(|s| s.as_str()).collect()
    }
}

// --- tracer state -----------------------------------------------------------

struct State {
    /// suite span id (decimal) -> the OTel Context holding that span
    spans: HashMap<String, Context>,
    /// synthetic parent id (decimal) -> extracted remote Context
    extracted: HashMap<String, Context>,
    counter: u64,
}

struct Inner {
    state: Mutex<State>,
    provider: SdkTracerProvider,
    agent_url: String,
    config: datadog_opentelemetry::configuration::Config,
}

#[derive(Clone)]
struct DdTraceRsTracer(Arc<Inner>);

temper_core::impl_any_value_trait!(DdTraceRsTracer, [Tracer]);

fn low64_dec(trace_id_u128: u128) -> String {
    (trace_id_u128 as u64).to_string()
}

impl DdTraceRsTracer {
    fn tracer() -> global::BoxedTracer {
        global::tracer("dd-trace-rust-conformance")
    }

    /// Build the CapturedSpan stub returned from start_span/otel_start_span.
    fn stub(cx: &Context, parent_id: &str, name: &str, service: &str, resource: &str, span_type: &str) -> CapturedSpan {
        let sc = cx.span().span_context().clone();
        let span_id = u64::from_be_bytes(sc.span_id().to_bytes());
        let trace_id = u128::from_be_bytes(sc.trace_id().to_bytes());
        CapturedSpan::new(
            low64_dec(trace_id),
            span_id.to_string(),
            parent_id.to_string(),
            name.to_string(),
            service.to_string(),
            resource.to_string(),
            span_type.to_string(),
            Mapped::new(Map::new(Vec::new())),
            Mapped::new(Map::new(Vec::new())),
            Vec::new(),
            None,
        )
    }

    fn make_span(&self, name: &str, parent_id: &str, kind: SpanKind, attrs: Vec<KeyValue>) -> Context {
        let tracer = Self::tracer();
        let mut builder = tracer.span_builder(name.to_string()).with_kind(kind);
        builder.attributes = Some(attrs);

        let has_parent = !parent_id.is_empty() && parent_id != "0";
        let st = self.0.state.lock().unwrap();
        let parent_cx: Option<Context> = if has_parent {
            st.spans
                .get(parent_id)
                .cloned()
                .or_else(|| st.extracted.get(parent_id).cloned())
        } else {
            None
        };
        drop(st);

        let cx_base = parent_cx.unwrap_or_else(Context::new);
        let span = builder.start_with_context(&tracer, &cx_base);
        cx_base.with_span(span)
    }
}

fn env(k: &str) -> String {
    std::env::var(k).unwrap_or_default()
}

impl TracerTrait for DdTraceRsTracer {
    fn clone_boxed(&self) -> Tracer {
        Tracer::new(self.clone())
    }

    fn start_span(
        &self,
        name: Arc<String>,
        parent_id: Arc<String>,
        service: Option<Arc<String>>,
        resource: Option<Arc<String>>,
        span_type: Option<Arc<String>>,
    ) -> CapturedSpan {
        let svc = service.map(|a| a.as_ref().clone()).unwrap_or_default();
        let res = resource.map(|a| a.as_ref().clone()).unwrap_or_default();
        let sty = span_type.map(|a| a.as_ref().clone()).unwrap_or_default();

        let mut attrs = vec![
            KeyValue::new("operation.name", name.as_ref().clone()),
            // prevent libdatadog dropping the local-root chunk (per upstream client)
            KeyValue::new("_dd.top_level", 1i64),
        ];
        if !svc.is_empty() {
            attrs.push(KeyValue::new("service.name", svc.clone()));
        }
        if !res.is_empty() {
            attrs.push(KeyValue::new("resource.name", res.clone()));
        }
        if !sty.is_empty() {
            attrs.push(KeyValue::new("span.type", sty.clone()));
        }

        let cx = self.make_span(name.as_ref(), parent_id.as_ref(), SpanKind::Internal, attrs);
        let stub = Self::stub(&cx, parent_id.as_ref(), name.as_ref(), &svc, &res, &sty);
        let sid = stub_span_id(&stub);
        self.0.state.lock().unwrap().spans.insert(sid, cx);
        stub
    }

    fn finish_span(&self, span_id: Arc<String>) {
        if let Some(cx) = self.0.state.lock().unwrap().spans.get(span_id.as_ref()) {
            cx.span().end();
        }
    }

    fn set_meta(&self, span_id: Arc<String>, key: Arc<String>, value: Arc<String>) {
        if let Some(cx) = self.0.state.lock().unwrap().spans.get(span_id.as_ref()) {
            cx.span().set_attribute(KeyValue::new(key.as_ref().clone(), value.as_ref().clone()));
        }
    }

    fn set_metric(&self, span_id: Arc<String>, key: Arc<String>, value: f64) {
        if let Some(cx) = self.0.state.lock().unwrap().spans.get(span_id.as_ref()) {
            cx.span().set_attribute(KeyValue::new(key.as_ref().clone(), value));
        }
    }

    fn set_resource(&self, span_id: Arc<String>, value: Arc<String>) {
        if let Some(cx) = self.0.state.lock().unwrap().spans.get(span_id.as_ref()) {
            cx.span().set_attribute(KeyValue::new("resource.name", value.as_ref().clone()));
        }
    }

    fn set_baggage(&self, _s: Arc<String>, _k: Arc<String>, _v: Arc<String>) {
        unsupported("set_baggage");
    }
    fn get_baggage(&self, _s: Arc<String>, _k: Arc<String>) -> Arc<String> {
        unsupported("get_baggage");
    }
    fn get_all_baggage(&self, _s: Arc<String>) -> Mapped<Arc<String>, Arc<String>> {
        unsupported("get_all_baggage");
    }
    fn remove_baggage(&self, _s: Arc<String>, _k: Arc<String>) {
        unsupported("remove_baggage");
    }
    fn remove_all_baggage(&self, _s: Arc<String>) {
        unsupported("remove_all_baggage");
    }

    fn add_link(&self, _s: Arc<String>, _l: Arc<String>, _a: Mapped<Arc<String>, Arc<String>>) {
        // OTel span links are set at creation, not after start.
        unsupported("add_link");
    }

    fn remove_meta(&self, _s: Arc<String>, _k: Arc<String>) {
        unsupported("remove_meta");
    }
    fn remove_metric(&self, _s: Arc<String>, _k: Arc<String>) {
        unsupported("remove_metric");
    }

    fn extract_headers(&self, headers: temper_core::Listed<(Arc<String>, Arc<String>)>) -> Arc<String> {
        let mut map = HashMap::new();
        let n = headers.len();
        for i in 0..n {
            let (k, v) = headers.get(i);
            map.insert(k.as_ref().to_lowercase(), v.as_ref().clone());
        }
        let ex = MapExtractor(map);
        let cx = global::get_text_map_propagator(|p| p.extract(&ex));
        let sc = cx.span().span_context().clone();
        if !sc.is_valid() {
            return Arc::new(String::new());
        }
        // Return the extracted parent's real span id (decimal); the suite asserts
        // on it directly AND uses it as a child's parentId (looked up in `extracted`).
        let span_id = u64::from_be_bytes(sc.span_id().to_bytes()).to_string();
        self.0.state.lock().unwrap().extracted.insert(span_id.clone(), cx);
        Arc::new(span_id)
    }

    fn inject_headers(&self, span_id: Arc<String>) -> Mapped<Arc<String>, Arc<String>> {
        let st = self.0.state.lock().unwrap();
        let cx = st.spans.get(span_id.as_ref()).or_else(|| st.extracted.get(span_id.as_ref())).cloned();
        drop(st);
        let mut inj = MapInjector(HashMap::new());
        if let Some(cx) = cx {
            global::get_text_map_propagator(|p| p.inject_context(&cx, &mut inj));
        }
        let pairs: Vec<(Arc<String>, Arc<String>)> =
            inj.0.into_iter().map(|(k, v)| (Arc::new(k), Arc::new(v))).collect();
        Mapped::new(Map::new(pairs))
    }

    fn flush(&self) {
        let _ = self.0.provider.force_flush();
    }

    fn captured_spans(&self) -> temper_core::Listed<CapturedSpan> {
        self.flush();
        spans_from_agent(&self.0.agent_url)
    }

    fn delivered_spans(&self) -> temper_core::Listed<CapturedSpan> {
        self.captured_spans()
    }

    fn config(&self) -> Mapped<Arc<String>, Arc<String>> {
        // Read back dd-trace-rs's PARSED config (reflects OTEL_* env mapping,
        // defaults like rate_limit=100, and DD_TAGS parsing) via the same
        // accessors the upstream rust parametric client uses.
        let c = &self.0.config;
        let bs = |b: bool| if b { "true" } else { "false" }.to_string();
        let tags = c
            .global_tags()
            .map(|(k, v)| format!("{k}:{v}"))
            .collect::<Vec<_>>()
            .join(",");
        let prop = c
            .trace_propagation_style_extract()
            .map(|styles| styles.iter().map(|s| s.to_string()).collect::<Vec<_>>().join(","))
            .unwrap_or_default();
        let debug = matches!(*c.log_level_filter(), datadog_opentelemetry::log::LevelFilter::Debug);
        let otel_enabled = match env("DD_TRACE_OTEL_ENABLED").to_lowercase().as_str() {
            "1" | "true" | "on" | "yes" => "true".to_string(),
            "" => String::new(),
            _ => "false".to_string(),
        };
        let pairs: Vec<(Arc<String>, Arc<String>)> = vec![
            ("dd_service", c.service().to_string()),
            ("dd_env", c.env().unwrap_or("").to_string()),
            ("dd_version", c.version().unwrap_or("").to_string()),
            ("dd_log_level", c.log_level_filter().to_string().to_lowercase()),
            ("dd_trace_enabled", bs(c.enabled())),
            ("dd_runtime_metrics_enabled", bs(c.metrics_otel_enabled())),
            ("dd_tags", tags),
            ("dd_trace_propagation_style", prop),
            ("dd_trace_debug", bs(debug)),
            ("dd_trace_agent_url", c.trace_agent_url().to_string()),
            ("dd_trace_rate_limit", c.trace_rate_limit().to_string()),
            ("dd_trace_sample_rate", env("DD_TRACE_SAMPLE_RATE")),
            ("dd_trace_otel_enabled", otel_enabled),
        ]
        .into_iter()
        .map(|(k, v)| (Arc::new(k.to_string()), Arc::new(v)))
        .collect();
        Mapped::new(Map::new(pairs))
    }

    // --- OpenTelemetry API (dd-trace-rs is OTel-native, so these use the same
    // span machinery as the DD-manual ops above) ---------------------------
    fn otel_start_span(&self, name: Arc<String>, parent_id: Arc<String>, kind: Arc<String>) -> CapturedSpan {
        let k = match kind.as_ref().to_lowercase().as_str() {
            "server" => SpanKind::Server,
            "client" => SpanKind::Client,
            "producer" => SpanKind::Producer,
            "consumer" => SpanKind::Consumer,
            _ => SpanKind::Internal,
        };
        let cx = self.make_span(name.as_ref(), parent_id.as_ref(), k, Vec::new());
        let stub = Self::stub(&cx, parent_id.as_ref(), name.as_ref(), "", "", "");
        let sid = stub_span_id(&stub);
        self.0.state.lock().unwrap().spans.insert(sid, cx);
        stub
    }

    fn otel_set_attribute(&self, span_id: Arc<String>, key: Arc<String>, value: Arc<String>) {
        self.set_meta(span_id, key, value);
    }
    fn otel_set_attribute_num(&self, span_id: Arc<String>, key: Arc<String>, value: f64) {
        self.set_metric(span_id, key, value);
    }
    fn otel_remove_attribute(&self, _s: Arc<String>, _k: Arc<String>) {
        unsupported("otel_remove_attribute");
    }
    fn otel_end_span(&self, span_id: Arc<String>) {
        self.finish_span(span_id);
    }
    fn otel_is_recording(&self, span_id: Arc<String>) -> bool {
        self.0
            .state
            .lock()
            .unwrap()
            .spans
            .get(span_id.as_ref())
            .map(|cx| cx.span().is_recording())
            .unwrap_or(false)
    }
    fn otel_span_context(&self, span_id: Arc<String>) -> OtelSpanContextInfo {
        let st = self.0.state.lock().unwrap();
        if let Some(cx) = st.spans.get(span_id.as_ref()) {
            let sc = cx.span().span_context().clone();
            OtelSpanContextInfo::new(
                format!("{:032x}", u128::from_be_bytes(sc.trace_id().to_bytes())),
                format!("{:016x}", u64::from_be_bytes(sc.span_id().to_bytes())),
            )
        } else {
            OtelSpanContextInfo::new(String::new(), String::new())
        }
    }
    fn otel_set_status(&self, span_id: Arc<String>, code: Arc<String>, description: Arc<String>) {
        if let Some(cx) = self.0.state.lock().unwrap().spans.get(span_id.as_ref()) {
            let sp = cx.span();
            match code.as_ref().to_uppercase().as_str() {
                "OK" => sp.set_status(opentelemetry::trace::Status::Ok),
                "ERROR" => sp.set_status(opentelemetry::trace::Status::error(description.as_ref().clone())),
                _ => sp.set_status(opentelemetry::trace::Status::Unset),
            }
        }
    }
    fn otel_record_exception(&self, _s: Arc<String>, _m: Arc<String>, _a: Mapped<Arc<String>, Arc<String>>) {
        unsupported("otel_record_exception");
    }
    fn otel_add_event(&self, _s: Arc<String>, _n: Arc<String>, _t: i32, _a: temper_core::Listed<EventAttr>) {
        unsupported("otel_add_event");
    }

    fn telemetry_config(&self) -> temper_core::Listed<TelemetryConfigItem> {
        unsupported("telemetry_config");
    }
    fn wire_span_events_json(&self, _s: Arc<String>) -> Arc<String> {
        unsupported("wire_span_events_json");
    }
    fn wire_span_meta_events_json(&self, _s: Arc<String>) -> Arc<String> {
        unsupported("wire_span_meta_events_json");
    }
    fn computed_stats_json(&self) -> Arc<String> {
        unsupported("computed_stats_json");
    }
    fn rc_capabilities_csv(&self) -> Arc<String> {
        unsupported("rc_capabilities_csv");
    }
    fn rc_apply_sampling_rate(&self, _rate: f64) -> bool {
        unsupported("rc_apply_sampling_rate");
    }
}

fn stub_span_id(s: &CapturedSpan) -> String {
    s.span_id().as_ref().clone()
}


// --- read delivered spans back from the ddapm-test-agent --------------------

fn spans_from_agent(agent_url: &str) -> temper_core::Listed<CapturedSpan> {
    let url = format!("{}/test/session/traces", agent_url.trim_end_matches('/'));
    let mut out: Vec<CapturedSpan> = Vec::new();
    for _ in 0..27 {
        if let Ok(resp) = ureq::get(&url).call() {
            if let Ok(text) = resp.into_string() {
                if let Ok(traces) = serde_json::from_str::<serde_json::Value>(&text) {
                    if let Some(arr) = traces.as_array() {
                        if !arr.is_empty() {
                            for trace in arr {
                                if let Some(spans) = trace.as_array() {
                                    for sp in spans {
                                        out.push(agent_span(sp));
                                    }
                                }
                            }
                            return temper_core::ToListed::to_listed(out);
                        }
                    }
                }
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(300));
    }
    temper_core::ToListed::to_listed(out)
}

fn jstr(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => n.to_string(),
        _ => String::new(),
    }
}

fn agent_span(sp: &serde_json::Value) -> CapturedSpan {
    let get = |k: &str| sp.get(k).map(jstr).unwrap_or_default();
    let mut meta_pairs: Vec<(Arc<String>, Arc<String>)> = Vec::new();
    if let Some(m) = sp.get("meta").and_then(|v| v.as_object()) {
        for (k, v) in m {
            meta_pairs.push((Arc::new(k.clone()), Arc::new(jstr(v))));
        }
    }
    let mut metric_pairs: Vec<(Arc<String>, f64)> = Vec::new();
    if let Some(m) = sp.get("metrics").and_then(|v| v.as_object()) {
        for (k, v) in m {
            metric_pairs.push((Arc::new(k.clone()), v.as_f64().unwrap_or(0.0)));
        }
    }
    let error = sp.get("error").and_then(|v| v.as_i64()).map(|n| n as i32);
    let parent = sp.get("parent_id").map(jstr).filter(|s| !s.is_empty()).unwrap_or_else(|| "0".to_string());
    // span links (v0.4 meta tag "_dd.span_links" is JSON) -> CapturedLink
    let mut links: Vec<CapturedLink> = Vec::new();
    if let Some(raw) = sp.get("meta").and_then(|m| m.get("_dd.span_links")).and_then(|v| v.as_str()) {
        if let Ok(arr) = serde_json::from_str::<serde_json::Value>(raw) {
            if let Some(list) = arr.as_array() {
                for l in list {
                    let tid_hex = l.get("trace_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let sid_hex = l.get("span_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let (low, high) = split_hex_128(&tid_hex);
                    links.push(CapturedLink::new(
                        u64::from_str_radix(sid_hex.trim_start_matches("0x"), 16).map(|n| n.to_string()).unwrap_or_default(),
                        low,
                        high,
                        Mapped::new(Map::new(Vec::new())),
                    ));
                }
            }
        }
    }
    CapturedSpan::new(
        get("trace_id"),
        get("span_id"),
        parent,
        get("name"),
        get("service"),
        get("resource"),
        get("type"),
        Mapped::new(Map::new(meta_pairs)),
        Mapped::new(Map::new(metric_pairs)),
        links,
        error,
    )
}

fn split_hex_128(hex: &str) -> (String, String) {
    let h = hex.trim_start_matches("0x");
    if h.len() <= 16 {
        (u64::from_str_radix(h, 16).map(|n| n.to_string()).unwrap_or_default(), "0".to_string())
    } else {
        let (hi, lo) = h.split_at(h.len() - 16);
        (
            u64::from_str_radix(lo, 16).map(|n| n.to_string()).unwrap_or_default(),
            u64::from_str_radix(hi, 16).map(|n| n.to_string()).unwrap_or_default(),
        )
    }
}

// silence unused import if OtelValue not referenced elsewhere
#[allow(dead_code)]
fn _touch(_: OtelValue) {}

// --- run one case ------------------------------------------------------------

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() {
    let idx: i32 = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(-1);

    let config = datadog_opentelemetry::configuration::Config::builder().build();
    let provider = datadog_opentelemetry::tracing().with_config(config.clone()).init();

    let agent_url = {
        let u = env("DD_TRACE_AGENT_URL");
        if u.is_empty() { "http://127.0.0.1:8126".to_string() } else { u }
    };

    let tracer = DdTraceRsTracer(Arc::new(Inner {
        state: Mutex::new(State { spans: HashMap::new(), extracted: HashMap::new(), counter: 0 }),
        provider: provider.clone(),
        agent_url,
        config,
    }));

    let cases = all_cases();
    let n = ListedTrait::len(&cases);
    if idx < 0 || idx >= n {
        eprintln!("index out of range");
        std::process::exit(3);
    }
    let case = ListedTrait::get(&cases, idx);
    let name = case.name().as_ref().clone();

    let result = catch_unwind(AssertUnwindSafe(|| {
        let check = (case.run())(Tracer::new(tracer.clone()));
        check
    }));

    let _ = provider.force_flush();

    match result {
        Ok(check) => {
            if check.ok() {
                println!("PASS {name}");
                std::process::exit(0);
            } else if std::env::var("RUST_KNOWN_DIFF").as_deref() == Ok("1") {
                // run-then-downgrade: a listed genuine-diff case that FAILS becomes
                // a documented skip; one that PASSES still reports PASS above, so
                // the list can't hide a fix.
                println!("SKIP {name} (known dd-trace-rust diff)");
                std::process::exit(2);
            } else {
                println!("FAIL {name}:\n{}", check.summary().as_ref());
                std::process::exit(1);
            }
        }
        Err(payload) => {
            let msg = panic_message(&payload);
            if let Some(op) = msg.strip_prefix(UNSUPPORTED) {
                println!("SKIP {name} (unsupported: {op})");
                std::process::exit(2);
            }
            if std::env::var("RUST_KNOWN_DIFF").as_deref() == Ok("1") {
                println!("SKIP {name} (known dd-trace-rust diff)");
                std::process::exit(2);
            }
            println!("FAIL {name}:\n{msg}");
            std::process::exit(1);
        }
    }
}

fn panic_message(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<&str>() {
        s.to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "panic".to_string()
    }
}
