use axum::{
    routing::{get, post, Router},
    Json,
};
use serde::{Deserialize, Serialize};

use crate::AppState;

#[derive(Debug, Deserialize)]
struct StartSpanArgs {
    name: String,
    parent_id: Option<u64>,
    service: Option<String>,
    #[serde(rename = "type")]
    span_type: Option<String>,
    resource: Option<String>,
    span_tags: Vec<(String, String)>,
}

#[derive(Debug, Serialize)]
struct StartSpanReturn {
    span_id: u64,
    trace_id: u64,
}

pub fn app() -> Router<AppState> {
    Router::new()
        // Basic trace operations
        .route("/crash", get(trace_crash))
        
        // Span operations
        .route("/span/start", post(trace_span_start))
        .route("/span/finish", post(trace_span_finish))
        .route("/span/set_meta", post(trace_span_set_meta))
        .route("/span/set_resource", post(trace_span_set_resource))
        .route("/span/set_metric", post(trace_span_set_metric))
        .route("/span/inject_headers", post(trace_span_inject_headers))
        .route("/span/extract_headers", post(trace_span_extract_headers))
        .route("/span/flush", post(trace_spans_flush))
        .route("/span/error", post(trace_span_error))
        .route("/span/add_link", post(trace_span_add_link))
        .route("/span/add_event", post(trace_span_add_event))
        .route("/span/current", get(trace_span_current))
        
        // Baggage operations
        .route("/span/set_baggage", post(trace_set_baggage))
        .route("/span/get_baggage", get(trace_get_baggage))
        .route("/span/get_all_baggage", get(trace_get_all_baggage))
        .route("/span/remove_baggage", post(trace_remove_baggage))
        .route("/span/remove_all_baggage", post(trace_remove_all_baggage))
        
        // Configuration and stats
        .route("/config", get(trace_config))
        .route("/stats/flush", post(trace_stats_flush))
}

async fn trace_span_start(
    Json(args): Json<StartSpanArgs>,
) -> Json<StartSpanReturn> {
    let mut builder = get_tracer().span_builder(args.name.clone());
    // hack to prevent libdatadog from dropping trace chunks
    let mut attributes = vec![opentelemetry::KeyValue::new("_dd.top_level".to_string(), 1)];
    attributes.append(&mut parse_attributes(args.attributes.as_ref()));
    
    // Add span tags to attributes
    for (key, value) in args.span_tags {
        attributes.push(opentelemetry::KeyValue::new(key, value));
    }
    
    // Add operation name as an attribute, maybe can remove this
    attributes.push(opentelemetry::KeyValue::new("operation.name", args.name.clone()));
    
    builder = builder.with_attributes(attributes);
    
    // Add service name as a resource if provided
    if let Some(service) = args.service {
        let resource = opentelemetry::Resource::new(vec![
            opentelemetry::KeyValue::new("service.name", service),
        ]);
        builder = builder.with_resource(resource);
    }

    // Add resource name as a resource if provided
    if let Some(resource) = args.resource {
        let resource = opentelemetry::Resource::new(vec![
            opentelemetry::KeyValue::new("resource.name", resource),
        ]);
        builder = builder.with_resource(resource);
    }
    let id = span.span_context().span_id();
    let span_id = u64::from_be_bytes(id.to_bytes());
    let trace_id = u64::from_be_bytes(
        span.span_context().trace_id().to_bytes()[8..16]
            .try_into()
            .unwrap(),
    );

    let ctx = Context::current_with_span(span);
    state.current_context.lock().unwrap().clone_from(&ctx);
    state.contexts.lock().unwrap().insert(span_id, ctx);

    debug!("created otel span {span_id}");
    
    builder.start(get_tracer())
    Json(StartSpanReturn {
        span_id: 0,
        trace_id: 0,
    })
}

async fn trace_crash() {}
async fn trace_span_finish() {}
async fn trace_span_set_meta() {}
async fn trace_span_set_resource() {}
async fn trace_span_set_metric() {}
async fn trace_span_inject_headers() {}
async fn trace_span_extract_headers() {}
async fn trace_spans_flush() {}
async fn trace_span_error() {}
async fn trace_span_add_link() {}
async fn trace_span_add_event() {}
async fn trace_span_current() {}
async fn trace_set_baggage() {}
async fn trace_get_baggage() {}
async fn trace_get_all_baggage() {}
async fn trace_remove_baggage() {}
async fn trace_remove_all_baggage() {}
async fn trace_config() {}
async fn trace_stats_flush() {} 