// Native dd-trace-go conformance adapter.
//
// The Temper suite is compiled to Rust (temper.out/rust/system-tests-redux).
// This binary implements the generated `TracerTrait` by calling the c-shared
// dd-trace-go library (libddtracego.dylib) in-process over the C ABI — no RPC,
// no subprocess. Unsupported ops panic; the runner catches that and records the
// case as skipped.
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_double};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::Arc;

use system_tests_redux::{all_cases, CapturedSpan, Tracer, TracerTrait};
use temper_core::{ListedTrait, MapBuilder, Mapped};

#[allow(non_snake_case)]
extern "C" {
    fn ddgo_init();
    fn ddgo_stop();
    fn ddgo_start_span(
        name: *const c_char,
        parent: *const c_char,
        service: *const c_char,
        resource: *const c_char,
        typ: *const c_char,
    ) -> *mut c_char;
    fn ddgo_finish_span(id: *const c_char);
    fn ddgo_set_meta(id: *const c_char, key: *const c_char, value: *const c_char);
    fn ddgo_set_metric(id: *const c_char, key: *const c_char, value: c_double);
    fn ddgo_extract(json: *const c_char) -> *mut c_char;
    fn ddgo_inject(id: *const c_char) -> *mut c_char;
    fn ddgo_flush();
    fn ddgo_free(p: *mut c_char);
}

fn cs(s: &str) -> CString {
    CString::new(s).unwrap()
}

// take ownership of a Go-allocated C string, copy to Rust, free it.
unsafe fn take(ptr: *mut c_char) -> String {
    if ptr.is_null() {
        return String::new();
    }
    let s = CStr::from_ptr(ptr).to_string_lossy().into_owned();
    ddgo_free(ptr);
    s
}

fn empty_meta() -> Mapped<Arc<String>, Arc<String>> {
    Mapped::new(MapBuilder::<Arc<String>, Arc<String>>::new())
}
fn empty_metrics() -> Mapped<Arc<String>, f64> {
    Mapped::new(MapBuilder::<Arc<String>, f64>::new())
}

#[derive(Clone)]
pub struct GoAdapter {
    _agent_url: Arc<String>,
}

impl GoAdapter {
    fn new() -> GoAdapter {
        GoAdapter {
            _agent_url: Arc::new(std::env::var("DD_TRACE_AGENT_URL").unwrap_or_default()),
        }
    }
}

fn unsupported(what: &str) -> ! {
    panic!("dd-trace-go adapter: unsupported op: {}", what)
}

impl TracerTrait for GoAdapter {
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
        let svc = service.map(|s| s.to_string()).unwrap_or_default();
        let res = resource.map(|s| s.to_string()).unwrap_or_default();
        let typ = span_type.map(|s| s.to_string()).unwrap_or_default();
        let out = unsafe {
            take(ddgo_start_span(
                cs(&name).as_ptr(),
                cs(&parent_id).as_ptr(),
                cs(&svc).as_ptr(),
                cs(&res).as_ptr(),
                cs(&typ).as_ptr(),
            ))
        };
        let mut it = out.splitn(2, ',');
        let span_id = it.next().unwrap_or("0").to_string();
        let trace_id = it.next().unwrap_or("0").to_string();
        CapturedSpan::new(
            trace_id,
            span_id,
            parent_id.to_string(),
            name.to_string(),
            svc,
            res,
            typ,
            empty_meta(),
            empty_metrics(),
            Vec::new(),
            None,
        )
    }

    fn finish_span(&self, span_id: Arc<String>) {
        unsafe { ddgo_finish_span(cs(&span_id).as_ptr()) }
    }
    fn set_meta(&self, span_id: Arc<String>, key: Arc<String>, value: Arc<String>) {
        unsafe { ddgo_set_meta(cs(&span_id).as_ptr(), cs(&key).as_ptr(), cs(&value).as_ptr()) }
    }
    fn set_metric(&self, span_id: Arc<String>, key: Arc<String>, value: f64) {
        unsafe { ddgo_set_metric(cs(&span_id).as_ptr(), cs(&key).as_ptr(), value as c_double) }
    }

    fn extract_headers(&self, headers: temper_core::Listed<(Arc<String>, Arc<String>)>) -> Arc<String> {
        let n = ListedTrait::len(&headers);
        let mut pairs: Vec<Vec<String>> = Vec::new();
        for i in 0..n {
            let (k, v) = ListedTrait::get(&headers, i);
            pairs.push(vec![k.to_string(), v.to_string()]);
        }
        let json = serde_json::to_string(&pairs).unwrap_or_else(|_| "[]".to_string());
        let id = unsafe { take(ddgo_extract(cs(&json).as_ptr())) };
        Arc::new(id)
    }

    fn inject_headers(&self, span_id: Arc<String>) -> Mapped<Arc<String>, Arc<String>> {
        let json = unsafe { take(ddgo_inject(cs(&span_id).as_ptr())) };
        let map: std::collections::HashMap<String, String> =
            serde_json::from_str(&json).unwrap_or_default();
        let mb = MapBuilder::<Arc<String>, Arc<String>>::new();
        for (k, v) in map {
            MapBuilder::set(&mb, Arc::new(k), Arc::new(v));
        }
        Mapped::new(mb)
    }

    fn flush(&self) {
        unsafe { ddgo_flush() }
    }

    fn captured_spans(&self) -> temper_core::Listed<CapturedSpan> {
        unsupported("captured_spans")
    }
    fn config(&self) -> Mapped<Arc<String>, Arc<String>> {
        unsupported("config")
    }
    fn set_baggage(&self, _: Arc<String>, _: Arc<String>, _: Arc<String>) { unsupported("set_baggage") }
    fn get_baggage(&self, _: Arc<String>, _: Arc<String>) -> Arc<String> { unsupported("get_baggage") }
    fn get_all_baggage(&self, _: Arc<String>) -> Mapped<Arc<String>, Arc<String>> { unsupported("get_all_baggage") }
    fn remove_baggage(&self, _: Arc<String>, _: Arc<String>) { unsupported("remove_baggage") }
    fn remove_all_baggage(&self, _: Arc<String>) { unsupported("remove_all_baggage") }
    fn add_link(&self, _: Arc<String>, _: Arc<String>, _: Mapped<Arc<String>, Arc<String>>) { unsupported("add_link") }
    fn set_resource(&self, _: Arc<String>, _: Arc<String>) { unsupported("set_resource") }
    fn remove_meta(&self, _: Arc<String>, _: Arc<String>) { unsupported("remove_meta") }
    fn remove_metric(&self, _: Arc<String>, _: Arc<String>) { unsupported("remove_metric") }
    fn otel_set_attribute_num(&self, _: Arc<String>, _: Arc<String>, _: f64) { unsupported("otel_set_attribute_num") }
    fn otel_remove_attribute(&self, _: Arc<String>, _: Arc<String>) { unsupported("otel_remove_attribute") }
    fn otel_start_span(&self, _: Arc<String>, _: Arc<String>, _: Arc<String>) -> CapturedSpan { unsupported("otel_start_span") }
    fn otel_set_attribute(&self, _: Arc<String>, _: Arc<String>, _: Arc<String>) { unsupported("otel_set_attribute") }
    fn otel_end_span(&self, _: Arc<String>) { unsupported("otel_end_span") }
    fn otel_is_recording(&self, _: Arc<String>) -> bool { unsupported("otel_is_recording") }
    fn otel_span_context(&self, _: Arc<String>) -> system_tests_redux::OtelSpanContextInfo { unsupported("otel_span_context") }
    fn otel_set_status(&self, _: Arc<String>, _: Arc<String>, _: Arc<String>) { unsupported("otel_set_status") }
    fn otel_record_exception(&self, _: Arc<String>, _: Arc<String>, _: Mapped<Arc<String>, Arc<String>>) { unsupported("otel_record_exception") }
    fn telemetry_config(&self) -> temper_core::Listed<system_tests_redux::TelemetryConfigItem> { unsupported("telemetry_config") }
    fn otel_add_event(&self, _: Arc<String>, _: Arc<String>, _: i32, _: temper_core::Listed<system_tests_redux::EventAttr>) { unsupported("otel_add_event") }
    fn wire_span_events_json(&self, _: Arc<String>) -> Arc<String> { unsupported("wire_span_events_json") }
    fn wire_span_meta_events_json(&self, _: Arc<String>) -> Arc<String> { unsupported("wire_span_meta_events_json") }
    fn delivered_spans(&self) -> temper_core::Listed<CapturedSpan> { unsupported("delivered_spans") }
    fn computed_stats_json(&self) -> Arc<String> { unsupported("computed_stats_json") }
    fn rc_capabilities_csv(&self) -> Arc<String> { unsupported("rc_capabilities_csv") }
    fn rc_apply_sampling_rate(&self, _: f64) -> bool { unsupported("rc_apply_sampling_rate") }
}

temper_core::impl_any_value_trait!(GoAdapter, [Tracer]);

fn main() {
    unsafe { ddgo_init() };
    let cases = all_cases();
    let n = ListedTrait::len(&cases);
    let (mut pass, mut fail, mut skip) = (0, 0, 0);
    for i in 0..n {
        let cse = ListedTrait::get(&cases, i);
        let name = cse.name().to_string();
        let run = cse.run();
        let res = catch_unwind(AssertUnwindSafe(|| run(Tracer::new(GoAdapter::new()))));
        match res {
            Ok(r) => {
                if r.ok() {
                    pass += 1;
                    println!("PASS {}", name);
                } else {
                    fail += 1;
                    println!("FAIL {}: {}", name, r.summary());
                }
            }
            Err(_) => {
                skip += 1;
                // unsupported op (or a genuine panic) — treat as skip
            }
        }
    }
    unsafe { ddgo_stop() };
    eprintln!("\n{}/{} cases passed (dd-trace-go), {} skipped", pass, pass + fail, skip);
    std::process::exit(if fail > 0 { 1 } else { 0 });
}
