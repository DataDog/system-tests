//! dd-trace-ruby conformance shim (rust cdylib half).
//!
//! The Temper suite compiles to the `system-tests-redux` crate. A Ruby process
//! `Fiddle`-loads this cdylib and drives it. Ruby implements the suite's
//! `Tracer` as a single `Dispatch` callback; this shim's `CallbackTracer`
//! implements every `TracerTrait` method by forwarding to that callback as
//! JSON, per adapters/dd-trace-ruby/CONTRACT.md.
use std::cell::RefCell;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::Arc;

use serde_json::{json, Value};
use system_tests_redux::{
    all_cases, CapturedLink, CapturedSpan, EventAttr, OtelSpanContextInfo, TelemetryConfigItem,
    Tracer, TracerTrait,
};
use temper_core::{ListedTrait, Map, Mapped};

/// Ruby-provided callback: `(op, args_json) -> result_json`.
/// The returned pointer is a libc-malloc'd NUL-terminated UTF-8 JSON string;
/// rust reads it then `libc::free`s it.
type Dispatch = extern "C" fn(*const c_char, *const c_char) -> *mut c_char;

/// Panic-payload prefix used to funnel a `{"__unsupported__":true}` dispatch
/// result out through `catch_unwind` into the SKIP path.
const UNSUPPORTED_PREFIX: &str = "__STR_UNSUPPORTED__:";

// ---------------------------------------------------------------------------
// CallbackTracer
// ---------------------------------------------------------------------------

struct CallbackTracerInner {
    dispatch: Dispatch,
}

#[derive(Clone)]
pub struct CallbackTracer(Arc<CallbackTracerInner>);

impl CallbackTracer {
    fn new(dispatch: Dispatch) -> CallbackTracer {
        CallbackTracer(Arc::new(CallbackTracerInner { dispatch }))
    }

    /// Forward one Tracer call to Ruby: serialize `args`, invoke `dispatch`,
    /// free Ruby's returned string, and return the parsed JSON result.
    /// A `{"__unsupported__":true}` result panics with `UNSUPPORTED_PREFIX`.
    fn call(&self, op: &str, args: Value) -> Value {
        let args_json = serde_json::to_string(&args).expect("serialize args");
        let c_op = CString::new(op).expect("op has NUL");
        let c_args = CString::new(args_json).expect("args_json has NUL");
        let ret = (self.0.dispatch)(c_op.as_ptr(), c_args.as_ptr());
        if ret.is_null() {
            panic!("dispatch({op}) returned null");
        }
        // Copy out (lossy: never panic on non-UTF8) then free the Ruby buffer.
        let owned = {
            let s = unsafe { CStr::from_ptr(ret) }.to_string_lossy().into_owned();
            unsafe { libc::free(ret as *mut libc::c_void) };
            s
        };
        let value: Value = serde_json::from_str(&owned)
            .unwrap_or_else(|e| panic!("dispatch({op}) returned invalid JSON: {e}: {owned}"));
        // A Ruby-side exception is marshaled as {"__error__":"..."} (never thrown
        // across the C boundary); surface it as a caught FAIL.
        if let Some(err) = value.get("__error__").and_then(Value::as_str) {
            panic!("dispatch({op}) ruby error: {err}");
        }
        if value
            .get("__unsupported__")
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            panic!("{UNSUPPORTED_PREFIX}{op}");
        }
        value
    }
}

temper_core::impl_any_value_trait!(CallbackTracer, [Tracer]);

// ---------------------------------------------------------------------------
// arg encoders (rust -> JSON), per CONTRACT "args_json"
// ---------------------------------------------------------------------------

fn s(v: &Arc<String>) -> Value {
    Value::String(v.as_ref().clone())
}

/// `Mapped<String,String>` -> JSON object (add_link attrs, otel_record_exception).
fn map_to_json(m: &Mapped<Arc<String>, Arc<String>>) -> Value {
    let obj = RefCell::new(serde_json::Map::new());
    m.for_each(&|k, v| {
        obj.borrow_mut()
            .insert(k.as_ref().clone(), Value::String(v.as_ref().clone()));
    });
    Value::Object(obj.into_inner())
}

/// `List<Entry<String,String>>` -> `[["k","v"],...]` (preserves dup keys).
fn headers_to_json(h: &temper_core::Listed<(Arc<String>, Arc<String>)>) -> Value {
    let n = h.len();
    let mut arr = Vec::with_capacity(n as usize);
    for i in 0..n {
        let (k, v) = h.get(i);
        arr.push(json!([k.as_ref().clone(), v.as_ref().clone()]));
    }
    Value::Array(arr)
}

/// `List<EventAttr>` -> `[{"key","kind","values":[..]}, ...]`.
fn events_to_json(attrs: &temper_core::Listed<EventAttr>) -> Value {
    let n = attrs.len();
    let mut arr = Vec::with_capacity(n as usize);
    for i in 0..n {
        let a = attrs.get(i);
        let vals = a.values();
        let vn = vals.len();
        let mut values = Vec::with_capacity(vn as usize);
        for j in 0..vn {
            values.push(Value::String(vals.get(j).as_ref().clone()));
        }
        arr.push(json!({
            "key": a.key().as_ref().clone(),
            "kind": a.kind().as_ref().clone(),
            "values": values,
        }));
    }
    Value::Array(arr)
}

// ---------------------------------------------------------------------------
// result decoders (JSON -> suite types), per CONTRACT "results"
// ---------------------------------------------------------------------------

fn as_str(v: &Value) -> String {
    v.as_str().unwrap_or("").to_string()
}

fn arc(v: &Value) -> Arc<String> {
    Arc::new(as_str(v))
}

fn field<'a>(v: &'a Value, key: &str) -> &'a Value {
    v.get(key).unwrap_or(&Value::Null)
}

fn build_str_map(v: &Value) -> Mapped<Arc<String>, Arc<String>> {
    let mut pairs: Vec<(Arc<String>, Arc<String>)> = Vec::new();
    if let Some(obj) = v.as_object() {
        for (k, val) in obj {
            pairs.push((Arc::new(k.clone()), Arc::new(as_str(val))));
        }
    }
    Mapped::new(Map::new(pairs))
}

fn build_num_map(v: &Value) -> Mapped<Arc<String>, f64> {
    let mut pairs: Vec<(Arc<String>, f64)> = Vec::new();
    if let Some(obj) = v.as_object() {
        for (k, val) in obj {
            pairs.push((Arc::new(k.clone()), val.as_f64().unwrap_or(0.0)));
        }
    }
    Mapped::new(Map::new(pairs))
}

fn parse_link(v: &Value) -> CapturedLink {
    CapturedLink::new(
        as_str(field(v, "span_id")),
        as_str(field(v, "trace_id")),
        {
            let h = field(v, "trace_id_high");
            if h.is_null() {
                "0".to_string()
            } else {
                as_str(h)
            }
        },
        build_str_map(field(v, "attributes")),
    )
}

fn parse_span(v: &Value) -> CapturedSpan {
    let links_val = field(v, "links");
    let mut links: Vec<CapturedLink> = Vec::new();
    if let Some(arr) = links_val.as_array() {
        for l in arr {
            links.push(parse_link(l));
        }
    }
    let error = field(v, "error").as_i64().map(|n| n as i32);
    CapturedSpan::new(
        as_str(field(v, "trace_id")),
        as_str(field(v, "span_id")),
        as_str(field(v, "parent_id")),
        as_str(field(v, "name")),
        as_str(field(v, "service")),
        as_str(field(v, "resource")),
        as_str(field(v, "span_type")),
        build_str_map(field(v, "meta")),
        build_num_map(field(v, "metrics")),
        links,
        error,
    )
}

fn parse_spans(v: &Value) -> temper_core::Listed<CapturedSpan> {
    let mut out: Vec<CapturedSpan> = Vec::new();
    if let Some(arr) = v.as_array() {
        for s in arr {
            out.push(parse_span(s));
        }
    }
    temper_core::ToListed::to_listed(out)
}

// ---------------------------------------------------------------------------
// TracerTrait: every method forwards to dispatch(op, args_json)
// ---------------------------------------------------------------------------

impl TracerTrait for CallbackTracer {
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
        // Suite defaults absent optional args to ""; encode positionally as ""
        // so Ruby always sees a fixed-arity 5-string arg array.
        let opt = |o: Option<Arc<String>>| Value::String(o.map(|a| a.as_ref().clone()).unwrap_or_default());
        let args = json!([s(&name), s(&parent_id), opt(service), opt(resource), opt(span_type)]);
        parse_span(&self.call("start_span", args))
    }

    fn finish_span(&self, span_id: Arc<String>) {
        self.call("finish_span", json!([s(&span_id)]));
    }

    fn set_meta(&self, span_id: Arc<String>, key: Arc<String>, value: Arc<String>) {
        self.call("set_meta", json!([s(&span_id), s(&key), s(&value)]));
    }

    fn set_metric(&self, span_id: Arc<String>, key: Arc<String>, value: f64) {
        self.call("set_metric", json!([s(&span_id), s(&key), value]));
    }

    fn set_baggage(&self, span_id: Arc<String>, key: Arc<String>, value: Arc<String>) {
        self.call("set_baggage", json!([s(&span_id), s(&key), s(&value)]));
    }

    fn get_baggage(&self, span_id: Arc<String>, key: Arc<String>) -> Arc<String> {
        arc(&self.call("get_baggage", json!([s(&span_id), s(&key)])))
    }

    fn get_all_baggage(&self, span_id: Arc<String>) -> Mapped<Arc<String>, Arc<String>> {
        build_str_map(&self.call("get_all_baggage", json!([s(&span_id)])))
    }

    fn remove_baggage(&self, span_id: Arc<String>, key: Arc<String>) {
        self.call("remove_baggage", json!([s(&span_id), s(&key)]));
    }

    fn remove_all_baggage(&self, span_id: Arc<String>) {
        self.call("remove_all_baggage", json!([s(&span_id)]));
    }

    fn add_link(
        &self,
        span_id: Arc<String>,
        link_to_span_id: Arc<String>,
        attributes: Mapped<Arc<String>, Arc<String>>,
    ) {
        self.call(
            "add_link",
            json!([s(&span_id), s(&link_to_span_id), map_to_json(&attributes)]),
        );
    }

    fn set_resource(&self, span_id: Arc<String>, value: Arc<String>) {
        self.call("set_resource", json!([s(&span_id), s(&value)]));
    }

    fn remove_meta(&self, span_id: Arc<String>, key: Arc<String>) {
        self.call("remove_meta", json!([s(&span_id), s(&key)]));
    }

    fn remove_metric(&self, span_id: Arc<String>, key: Arc<String>) {
        self.call("remove_metric", json!([s(&span_id), s(&key)]));
    }

    fn otel_set_attribute_num(&self, span_id: Arc<String>, key: Arc<String>, value: f64) {
        self.call("otel_set_attribute_num", json!([s(&span_id), s(&key), value]));
    }

    fn otel_remove_attribute(&self, span_id: Arc<String>, key: Arc<String>) {
        self.call("otel_remove_attribute", json!([s(&span_id), s(&key)]));
    }

    fn extract_headers(&self, headers: temper_core::Listed<(Arc<String>, Arc<String>)>) -> Arc<String> {
        arc(&self.call("extract_headers", json!([headers_to_json(&headers)])))
    }

    fn inject_headers(&self, span_id: Arc<String>) -> Mapped<Arc<String>, Arc<String>> {
        build_str_map(&self.call("inject_headers", json!([s(&span_id)])))
    }

    fn flush(&self) {
        self.call("flush", json!([]));
    }

    fn captured_spans(&self) -> temper_core::Listed<CapturedSpan> {
        parse_spans(&self.call("captured_spans", json!([])))
    }

    fn config(&self) -> Mapped<Arc<String>, Arc<String>> {
        build_str_map(&self.call("config", json!([])))
    }

    fn otel_start_span(&self, name: Arc<String>, parent_id: Arc<String>, kind: Arc<String>) -> CapturedSpan {
        parse_span(&self.call("otel_start_span", json!([s(&name), s(&parent_id), s(&kind)])))
    }

    fn otel_set_attribute(&self, span_id: Arc<String>, key: Arc<String>, value: Arc<String>) {
        self.call("otel_set_attribute", json!([s(&span_id), s(&key), s(&value)]));
    }

    fn otel_end_span(&self, span_id: Arc<String>) {
        self.call("otel_end_span", json!([s(&span_id)]));
    }

    fn otel_is_recording(&self, span_id: Arc<String>) -> bool {
        self.call("otel_is_recording", json!([s(&span_id)]))
            .as_bool()
            .unwrap_or(false)
    }

    fn otel_span_context(&self, span_id: Arc<String>) -> OtelSpanContextInfo {
        let v = self.call("otel_span_context", json!([s(&span_id)]));
        OtelSpanContextInfo::new(as_str(field(&v, "trace_id_hex")), as_str(field(&v, "span_id_hex")))
    }

    fn otel_set_status(&self, span_id: Arc<String>, code: Arc<String>, description: Arc<String>) {
        self.call("otel_set_status", json!([s(&span_id), s(&code), s(&description)]));
    }

    fn otel_record_exception(
        &self,
        span_id: Arc<String>,
        message: Arc<String>,
        attributes: Mapped<Arc<String>, Arc<String>>,
    ) {
        self.call(
            "otel_record_exception",
            json!([s(&span_id), s(&message), map_to_json(&attributes)]),
        );
    }

    fn telemetry_config(&self) -> temper_core::Listed<TelemetryConfigItem> {
        let v = self.call("telemetry_config", json!([]));
        let mut out: Vec<TelemetryConfigItem> = Vec::new();
        if let Some(arr) = v.as_array() {
            for item in arr {
                out.push(TelemetryConfigItem::new(
                    as_str(field(item, "name")),
                    as_str(field(item, "value")),
                    as_str(field(item, "origin")),
                ));
            }
        }
        temper_core::ToListed::to_listed(out)
    }

    fn otel_add_event(
        &self,
        span_id: Arc<String>,
        name: Arc<String>,
        time_micros: i32,
        attrs: temper_core::Listed<EventAttr>,
    ) {
        self.call(
            "otel_add_event",
            json!([s(&span_id), s(&name), time_micros, events_to_json(&attrs)]),
        );
    }

    fn wire_span_events_json(&self, span_id: Arc<String>) -> Arc<String> {
        arc(&self.call("wire_span_events_json", json!([s(&span_id)])))
    }

    fn wire_span_meta_events_json(&self, span_id: Arc<String>) -> Arc<String> {
        arc(&self.call("wire_span_meta_events_json", json!([s(&span_id)])))
    }

    fn delivered_spans(&self) -> temper_core::Listed<CapturedSpan> {
        parse_spans(&self.call("delivered_spans", json!([])))
    }

    fn computed_stats_json(&self) -> Arc<String> {
        arc(&self.call("computed_stats_json", json!([])))
    }

    fn rc_capabilities_csv(&self) -> Arc<String> {
        arc(&self.call("rc_capabilities_csv", json!([])))
    }

    fn rc_apply_sampling_rate(&self, rate: f64) -> bool {
        self.call("rc_apply_sampling_rate", json!([rate]))
            .as_bool()
            .unwrap_or(false)
    }
}

// ---------------------------------------------------------------------------
// C ABI (per CONTRACT.md)
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn str_case_count() -> i32 {
    ListedTrait::len(&all_cases())
}

#[no_mangle]
pub extern "C" fn str_case_name(index: i32) -> *mut c_char {
    let cases = all_cases();
    if index < 0 || index >= ListedTrait::len(&cases) {
        return std::ptr::null_mut();
    }
    to_cstring(ListedTrait::get(&cases, index).name().as_ref().clone())
}

#[no_mangle]
pub extern "C" fn str_free(p: *mut c_char) {
    if !p.is_null() {
        unsafe { drop(CString::from_raw(p)) };
    }
}

/// Build a C string for return across the boundary, never panicking: strip any
/// interior NUL (would make `CString::new` fail) so `unwrap` can't unwind into C.
fn to_cstring(s: String) -> *mut c_char {
    CString::new(s.replace('\0', "\u{fffd}")).unwrap_or_default().into_raw()
}

/// Run case `index` against a `CallbackTracer` wired to `dispatch`. Returns a
/// rust-malloc'd `"PASS <name>"` / `"FAIL <name>:\n<summary>"` /
/// `"SKIP <name> (<reason>)"`; free via `str_free`.
#[no_mangle]
pub extern "C" fn str_run_case(index: i32, dispatch: Dispatch) -> *mut c_char {
    let cases = all_cases();
    if index < 0 || index >= ListedTrait::len(&cases) {
        return std::ptr::null_mut();
    }
    let case = ListedTrait::get(&cases, index); // bounds-checked above: no OOB panic
    let name = case.name().as_ref().clone();

    let result = catch_unwind(AssertUnwindSafe(|| {
        let tracer = Tracer::new(CallbackTracer::new(dispatch));
        (case.run())(tracer)
    }));

    let out = match result {
        Ok(check) => {
            if check.ok() {
                format!("PASS {name}")
            } else {
                format!("FAIL {name}:\n{}", check.summary())
            }
        }
        Err(payload) => {
            let msg = panic_message(&payload);
            if let Some(op) = msg.strip_prefix(UNSUPPORTED_PREFIX) {
                format!("SKIP {name} (unsupported: {op})")
            } else {
                format!("FAIL {name}:\npanic: {msg}")
            }
        }
    };
    to_cstring(out)
}

fn panic_message(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

// ---------------------------------------------------------------------------
// Unit test: a stub dispatch (canned JSON) drives one real case end-to-end,
// proving CallbackTracer forwards args and parses results. (Ruby not required.)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use std::sync::Mutex;

    // Minimal stateful in-memory tracer, addressed through a C dispatch fn.
    struct StubSpan {
        trace_id: String,
        span_id: String,
        parent_id: String,
        name: String,
        service: String,
        resource: String,
        span_type: String,
        meta: BTreeMap<String, String>,
        metrics: BTreeMap<String, f64>,
    }

    struct StubState {
        next: u64,
        spans: Vec<StubSpan>,
    }

    static STATE: Mutex<Option<StubState>> = Mutex::new(None);

    fn malloc_json(v: &Value) -> *mut c_char {
        let bytes = serde_json::to_string(v).unwrap().into_bytes();
        unsafe {
            let p = libc::malloc(bytes.len() + 1) as *mut c_char;
            std::ptr::copy_nonoverlapping(bytes.as_ptr() as *const c_char, p, bytes.len());
            *p.add(bytes.len()) = 0;
            p
        }
    }

    fn span_to_json(sp: &StubSpan) -> Value {
        json!({
            "trace_id": sp.trace_id,
            "span_id": sp.span_id,
            "parent_id": sp.parent_id,
            "name": sp.name,
            "service": sp.service,
            "resource": sp.resource,
            "span_type": sp.span_type,
            "meta": sp.meta,
            "metrics": sp.metrics,
            "links": [],
            "error": Value::Null,
        })
    }

    extern "C" fn stub_dispatch(op: *const c_char, args_json: *const c_char) -> *mut c_char {
        let op = unsafe { CStr::from_ptr(op) }.to_str().unwrap();
        let args: Value =
            serde_json::from_str(unsafe { CStr::from_ptr(args_json) }.to_str().unwrap()).unwrap();
        let mut guard = STATE.lock().unwrap();
        let st = guard.as_mut().unwrap();
        let a = args.as_array().unwrap();
        let result = match op {
            "start_span" => {
                let name = a[0].as_str().unwrap().to_string();
                let parent_id = a[1].as_str().unwrap().to_string();
                st.next += 1;
                let span_id = (1_000_000 + st.next).to_string();
                let trace_id = st
                    .spans
                    .iter()
                    .find(|s| s.span_id == parent_id)
                    .map(|s| s.trace_id.clone())
                    .unwrap_or_else(|| span_id.clone());
                let sp = StubSpan {
                    trace_id,
                    span_id: span_id.clone(),
                    parent_id,
                    name,
                    service: a[2].as_str().unwrap().to_string(),
                    resource: a[3].as_str().unwrap().to_string(),
                    span_type: a[4].as_str().unwrap().to_string(),
                    meta: BTreeMap::new(),
                    metrics: BTreeMap::new(),
                };
                let out = span_to_json(&sp);
                st.spans.push(sp);
                out
            }
            "set_meta" => {
                let id = a[0].as_str().unwrap();
                if let Some(sp) = st.spans.iter_mut().find(|s| s.span_id == id) {
                    sp.meta
                        .insert(a[1].as_str().unwrap().to_string(), a[2].as_str().unwrap().to_string());
                }
                Value::Null
            }
            "set_metric" => {
                let id = a[0].as_str().unwrap();
                if let Some(sp) = st.spans.iter_mut().find(|s| s.span_id == id) {
                    sp.metrics
                        .insert(a[1].as_str().unwrap().to_string(), a[2].as_f64().unwrap());
                }
                Value::Null
            }
            "finish_span" | "flush" => Value::Null,
            "captured_spans" => {
                Value::Array(st.spans.iter().map(span_to_json).collect())
            }
            _ => json!({ "__unsupported__": true }),
        };
        malloc_json(&result)
    }

    #[test]
    fn top_level_attributes_via_stub_dispatch() {
        *STATE.lock().unwrap() = Some(StubState { next: 0, spans: Vec::new() });

        // Locate the case index by name (mirrors how Ruby will).
        let count = str_case_count();
        let mut index = -1;
        for i in 0..count {
            let p = str_case_name(i);
            let name = unsafe { CStr::from_ptr(p) }.to_str().unwrap().to_string();
            str_free(p);
            if name == "tracer.top_level_attributes" {
                index = i;
                break;
            }
        }
        assert!(index >= 0, "case tracer.top_level_attributes not found");

        let p = str_run_case(index, stub_dispatch);
        let result = unsafe { CStr::from_ptr(p) }.to_str().unwrap().to_string();
        str_free(p);
        eprintln!("stub-dispatch result: {result}");
        assert!(
            result.starts_with("PASS tracer.top_level_attributes"),
            "expected PASS, got: {result}"
        );
    }
}
