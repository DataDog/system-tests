mod dto;

use axum::{
    extract::{Json, State},
    http::{HeaderMap, HeaderName, StatusCode},
    routing::{get, post},
    Router,
};
use dto::*;
use opentelemetry::{
    baggage::BaggageExt,
    trace::{Span, Status, TraceContextExt, Tracer},
    Context,
};
use opentelemetry_http::HeaderExtractor;
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
    vec,
};
use tracing::debug;

use crate::{copy_baggage, get_tracer, AppState, ContextWithParent};

/// Fake span id for contexts without a valid remote span context (e.g. "restart" mode), so
/// they can still be stored and referenced as a `parent_id`. High bit avoids real span ids.
fn next_synthetic_span_id() -> u64 {
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    (1u64 << 63) | COUNTER.fetch_add(1, Ordering::Relaxed)
}

pub fn app() -> Router<AppState> {
    Router::new()
        .route("/span/start", post(start_span))
        .route("/span/current", get(current_span))
        .route("/span/finish", post(finish_span))
        .route("/span/set_resource", post(set_resource))
        .route("/span/set_meta", post(set_meta))
        .route("/span/set_metric", post(set_metric))
        .route("/span/manual_keep", post(manual_keep))
        .route("/span/manual_drop", post(manual_drop))
        .route("/span/error", post(set_error))
        .route("/span/add_link", post(add_link))
        .route("/span/add_event", post(add_event))
        .route("/crash", get(crash))
        .route("/span/inject_headers", post(inject_headers))
        .route("/span/extract_headers", post(extract_headers))
        .route("/span/flush", post(flush_spans))
        .route("/stats/flush", post(flush_stats))
        .route("/config", get(config))
        .route("/agent/ensure_agent_info", get(ensure_agent_info))
        .route("/span/set_baggage", post(set_baggage))
        .route("/span/get_baggage", get(get_baggage))
        .route("/span/get_all_baggage", get(get_all_baggage))
        .route("/span/remove_baggage", post(remove_baggage))
        .route("/span/remove_all_baggage", post(remove_all_baggage))
}

async fn ensure_agent_info() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "ready": true }))
}

// Handler implementations

async fn start_span(
    State(state): State<AppState>,
    Json(args): Json<StartSpanArgs>,
) -> Json<StartSpanResult> {
    let mut attributes = vec![];
    if let Some(service) = args.service {
        attributes.push(opentelemetry::KeyValue::new("service.name", service));
    }

    if let Some(resource) = args.resource {
        attributes.push(opentelemetry::KeyValue::new("resource.name", resource));
    }

    if let Some(span_type) = args.r#type {
        attributes.push(opentelemetry::KeyValue::new("span.type", span_type));
    }

    args.span_tags.iter().for_each(|tag| {
        debug!("start_span: add received tag {tag:?}");
        attributes.push(opentelemetry::KeyValue::new(
            tag.key.clone(),
            tag.value.clone(),
        ))
    });

    // is this ok? some tests don't pass without it
    attributes.push(opentelemetry::KeyValue::new(
        "operation.name",
        args.name.clone(),
    ));

    let builder = get_tracer()
        .span_builder(args.name.clone())
        .with_attributes(attributes);

    let parent_ctx = if let Some(parent_id) = args.parent_id {
        let contexts = state.contexts.lock().unwrap();
        if let Some(parent_ctx) = contexts.get(&parent_id) {
            debug!("build with span {parent_id:?} found");

            // Use the stored context as-is: it holds the live local parent span (and its
            // baggage). Wrapping it as a remote span context would make every child a new
            // local root for the span processor.
            Some(parent_ctx.context.clone())
        } else if let Some(parent_ctx) = state
            .extracted_span_contexts
            .lock()
            .unwrap()
            .get(&parent_id)
        {
            let parent = parent_ctx.clone();

            let parent_span_id =
                u64::from_be_bytes(parent.span().span_context().span_id().to_bytes());
            debug!(
                "build with extracted span child {}, hex: {}",
                parent_span_id,
                parent.span().span_context().span_id(),
            );
            Some(parent)
        } else {
            debug!("build with span {parent_id:?} NOT found");
            return Json(StartSpanResult::error());
        }
    } else {
        None
    };

    let span = if let Some(ref parent_ctx) = parent_ctx {
        builder.start_with_context(get_tracer(), parent_ctx)
    } else {
        builder.start(get_tracer())
    };

    let id = span.span_context().span_id();
    let span_id = u64::from_be_bytes(id.to_bytes());
    let trace_id = u128::from_be_bytes(span.span_context().trace_id().to_bytes());

    // Build from parent_ctx (not current) so baggage isn't dropped.
    let ctx = match &parent_ctx {
        Some(parent_ctx) => parent_ctx.with_span(span),
        None => Context::current_with_span(span),
    };

    let ctx_with_parent = Arc::new(ContextWithParent::new(ctx, parent_ctx));
    *state.current_context.lock().unwrap() = ctx_with_parent.clone();
    state
        .contexts
        .lock()
        .unwrap()
        .insert(span_id, ctx_with_parent.clone());

    debug!("created span {span_id} ");

    Json(StartSpanResult { span_id, trace_id })
}

async fn current_span(State(state): State<AppState>) -> Json<StartSpanResult> {
    let contexts = state.contexts.lock().unwrap();
    contexts
        .iter()
        .for_each(|(span_id, _)| debug!("current_span AppState span_id: {span_id}"));

    let ctx = state.current_context.lock().unwrap();
    let span = ctx.context.span();
    let span_id = u64::from_be_bytes(span.span_context().span_id().to_bytes());
    let trace_id = u128::from_be_bytes(span.span_context().trace_id().to_bytes());

    debug!("current_span {span_id} ");

    Json(StartSpanResult { span_id, trace_id })
}

async fn finish_span(State(state): State<AppState>, Json(args): Json<SpanFinishArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    let parent = if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        span.end();
        debug!("finish_span: span {} found", args.span_id);
        ctx.parent.clone()
    } else {
        debug!("finish_span: span {} NOT found", args.span_id);
        None
    };

    let current = parent
        .map(|parent| {
            contexts
                .get(&u64::from_be_bytes(
                    parent.span().span_context().span_id().to_bytes(),
                ))
                .cloned()
                .unwrap_or_default()
        })
        .unwrap_or_default();
    *state.current_context.lock().unwrap() = current;
}

async fn set_resource(State(state): State<AppState>, Json(args): Json<SpanSetResourceArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        debug!("set_resource: span {} found", args.span_id);
        // `resource.name` is the attribute dd-trace-rs maps to the span resource.
        span.set_attribute(opentelemetry::KeyValue::new(
            "resource.name".to_string(),
            args.resource.clone(),
        ));
    } else {
        debug!("set_resource: span {} NOT found", args.span_id);
    }
}

async fn set_meta(State(state): State<AppState>, Json(args): Json<SpanSetMetaArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        debug!("set_meta: span {} found", args.span_id);
        let value: Option<opentelemetry::Value> = match &args.value {
            serde_json::Value::String(s) => Some(s.clone().into()),
            serde_json::Value::Bool(b) => Some((*b).into()),
            serde_json::Value::Number(n) => Some(n.to_string().into()),
            // Lists of strings become native OTel arrays; nested lists can't be represented.
            serde_json::Value::Array(items) => items
                .iter()
                .map(|i| {
                    i.as_str()
                        .map(|s| opentelemetry::StringValue::from(s.to_string()))
                })
                .collect::<Option<Vec<_>>>()
                .map(|v| opentelemetry::Value::Array(v.into())),
            // OTel spans can't remove an attribute once set.
            serde_json::Value::Null | serde_json::Value::Object(_) => None,
        };
        match value {
            Some(value) => {
                span.set_attribute(opentelemetry::KeyValue::new(args.key.clone(), value))
            }
            None => debug!("set_meta: can't set {} to {}", args.key, args.value),
        }
    } else {
        debug!("set_meta: span {} NOT found", args.span_id);
    }
}

async fn set_metric(State(state): State<AppState>, Json(args): Json<SpanSetMetricArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        debug!("set_metric: span {} found", args.span_id);
        // Numeric attributes are exported as span metrics; strings would land in meta.
        match args.value {
            MetricValue::Number(value) => {
                span.set_attribute(opentelemetry::KeyValue::new(args.key.clone(), value))
            }
            MetricValue::IntArray(values) => span.set_attribute(opentelemetry::KeyValue::new(
                args.key.clone(),
                opentelemetry::Value::Array(values.into()),
            )),
            // OTel spans can't remove an attribute once set.
            MetricValue::Null => debug!("set_metric: removing {} is not supported", args.key),
        }
    } else {
        debug!("set_metric: span {} NOT found", args.span_id);
    }
}

async fn manual_keep(State(state): State<AppState>, Json(args): Json<ManualSamplingArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        debug!("manual_keep: span {} found", args.span_id);
        debug!("manual_keep: not implemented");
    } else {
        debug!("manual_keep: span {} NOT found", args.span_id);
    }
}

async fn manual_drop(State(state): State<AppState>, Json(args): Json<ManualSamplingArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        debug!("manual_drop: span {} found", args.span_id);
        debug!("manual_drop: not implemented");
    } else {
        debug!("manual_drop: span {} NOT found", args.span_id);
    }
}

async fn set_error(State(state): State<AppState>, Json(args): Json<SpanErrorArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.context.span();
        debug!("set_error: span {} found", args.span_id);
        // The exporter sets the dd span `error` flag from the OTel `Error` status, which also
        // feeds the client-side stats Errors count. `datadog.error` keeps it set as long as
        // error.message/error.type/error.stack are all present.
        span.set_status(Status::Error {
            description: args.message.clone().into(),
        });
        span.set_attribute(opentelemetry::KeyValue::new("datadog.error", 1i64));
        span.set_attribute(opentelemetry::KeyValue::new(
            "error.type".to_string(),
            args.r#type.clone(),
        ));
        span.set_attribute(opentelemetry::KeyValue::new(
            "error.message".to_string(),
            args.message.clone(),
        ));
        span.set_attribute(opentelemetry::KeyValue::new(
            "error.stack".to_string(),
            args.stack.clone(),
        ));
    } else {
        debug!("set_error: span {} NOT found", args.span_id);
    }
}

async fn add_link(State(state): State<AppState>, Json(args): Json<SpanAddLinkArgs>) {
    // The linked context can be a local span or one created by extract_headers.
    let linked = state
        .contexts
        .lock()
        .unwrap()
        .get(&args.parent_id)
        .map(|ctx| ctx.context.span().span_context().clone())
        .or_else(|| {
            state
                .extracted_span_contexts
                .lock()
                .unwrap()
                .get(&args.parent_id)
                .map(|ctx| ctx.span().span_context().clone())
        });
    let Some(linked) = linked.filter(|sc| sc.is_valid()) else {
        debug!(
            "add_link: linked span {} NOT found or invalid",
            args.parent_id
        );
        return;
    };
    if let Some(ctx) = state.contexts.lock().unwrap().get(&args.span_id) {
        ctx.context.span().add_link(
            linked,
            crate::opentelemetry::parse_attributes_native(args.attributes.as_ref()),
        );
    } else {
        debug!("add_link: span {} NOT found", args.span_id);
    }
}

async fn add_event(State(state): State<AppState>, Json(args): Json<SpanAddEventArgs>) {
    if let Some(ctx) = state.contexts.lock().unwrap().get(&args.span_id) {
        ctx.context.span().add_event_with_timestamp(
            args.name,
            std::time::UNIX_EPOCH + std::time::Duration::from_nanos(args.timestamp),
            crate::opentelemetry::parse_attributes_native(args.attributes.as_ref()),
        );
    } else {
        debug!("add_event: span {} NOT found", args.span_id);
    }
}

/// Crashes the process; the test only checks that the app goes down.
async fn crash() {
    std::process::abort();
}

async fn inject_headers(
    State(state): State<AppState>,
    Json(args): Json<SpanInjectHeadersArgs>,
) -> Json<SpanInjectHeadersResult> {
    let contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get(&args.span_id) {
        opentelemetry::global::get_text_map_propagator(|propagator| {
            let mut injector = HashMap::new();

            let context = &ctx.context;

            debug!("inject_headers: context: {:#?}", context);

            propagator.inject_context(context, &mut injector);

            debug!(
                "inject_headers: span {} found: {:#?}",
                args.span_id, injector
            );

            Json(SpanInjectHeadersResult {
                http_headers: injector
                    .iter()
                    .map(|(key, value)| KeyValue {
                        key: key.to_string(),
                        value: value.to_string(),
                    })
                    .collect(),
            })
        })
    } else {
        debug!("inject_headers: span {} NOT found", args.span_id);
        Json(SpanInjectHeadersResult {
            http_headers: vec![],
        })
    }
}

async fn extract_headers(
    State(state): State<AppState>,
    Json(args): Json<SpanExtractHeadersArgs>,
) -> Json<SpanExtractHeadersResult> {
    opentelemetry::global::get_text_map_propagator(|propagator| {
        // Repeated headers are kept as separate values: combining them is the tracer's job
        // (multi-value extraction). Headers that aren't valid HTTP are skipped rather than
        // panicking.
        let mut extractor = HeaderMap::new();
        for kv in &args.http_headers {
            let Ok(name) = kv.key.as_str().parse::<HeaderName>() else {
                debug!("extract_headers: skipping invalid header name {:?}", kv.key);
                continue;
            };
            match kv.value.parse() {
                Ok(value) => {
                    extractor.append(name, value);
                }
                Err(_) => debug!("extract_headers: skipping invalid value for {name}"),
            }
        }

        debug!("extract_headers: received {:#?}", extractor);

        let context = propagator.extract(&HeaderExtractor(&extractor));
        let span_id = if context.span().span_context().is_valid() {
            u64::from_be_bytes(context.span().span_context().span_id().to_bytes())
        } else {
            next_synthetic_span_id()
        };
        let trace_id = u128::from_be_bytes(context.span().span_context().trace_id().to_bytes());

        debug!("extract_headers: trace_id: {trace_id}, span_id: {span_id:#?}");

        state
            .extracted_span_contexts
            .lock()
            .unwrap()
            .insert(span_id, context);

        Json(SpanExtractHeadersResult {
            span_id: Some(span_id),
        })
    })
}

async fn flush_spans(State(state): State<AppState>) -> StatusCode {
    let result = state.tracer_provider.force_flush();
    state.contexts.lock().unwrap().clear();
    state.extracted_span_contexts.lock().unwrap().clear();
    *state.current_context.lock().unwrap() = Arc::new(ContextWithParent::default());
    debug!(
        "flush_spans: all spans and contexts cleared ok: {:?}",
        result
    );

    if result.is_ok() {
        StatusCode::OK
    } else {
        StatusCode::INTERNAL_SERVER_ERROR
    }
}

async fn flush_stats(State(state): State<AppState>) -> StatusCode {
    let result = state.tracer_provider.force_flush();
    if result.is_ok() {
        StatusCode::OK
    } else {
        StatusCode::INTERNAL_SERVER_ERROR
    }
}

async fn config(State(state): State<AppState>) -> Json<TraceConfigResponse> {
    Json(TraceConfigResponse {
        config: state.dd_config.into(),
    })
}

async fn set_baggage(State(state): State<AppState>, Json(args): Json<SpanSetBaggageArgs>) {
    let updated = state.update_context(args.span_id, |ctx| {
        let mut baggage = copy_baggage(ctx.baggage());
        let _ = baggage.insert(args.key.clone(), args.value.clone());
        ctx.with_baggage(baggage)
    });
    if updated.is_none() {
        debug!("set_baggage: span {} NOT found", args.span_id);
    }
}

async fn get_baggage(
    State(state): State<AppState>,
    Json(args): Json<SpanGetBaggageArgs>,
) -> Json<SpanGetBaggageResult> {
    let contexts = state.contexts.lock().unwrap();
    let baggage = contexts.get(&args.span_id).and_then(|ctx| {
        ctx.context
            .baggage()
            .get(&args.key)
            .map(|value| value.as_str().to_string())
    });
    Json(SpanGetBaggageResult { baggage })
}

async fn get_all_baggage(
    State(state): State<AppState>,
    Json(args): Json<SpanGetAllBaggageArgs>,
) -> Json<SpanGetAllBaggageResult> {
    let contexts = state.contexts.lock().unwrap();
    let baggage = contexts.get(&args.span_id).map(|ctx| {
        ctx.context
            .baggage()
            .iter()
            .map(|(key, (value, _))| (key.to_string(), value.as_str().to_string()))
            .collect()
    });
    Json(SpanGetAllBaggageResult { baggage })
}

async fn remove_baggage(State(state): State<AppState>, Json(args): Json<SpanRemoveBaggageArgs>) {
    let updated = state.update_context(args.span_id, |ctx| {
        let mut baggage = copy_baggage(ctx.baggage());
        let _ = baggage.remove(&args.key);
        ctx.with_baggage(baggage)
    });
    if updated.is_none() {
        debug!("remove_baggage: span {} NOT found", args.span_id);
    }
}

async fn remove_all_baggage(
    State(state): State<AppState>,
    Json(args): Json<SpanRemoveAllBaggageArgs>,
) {
    if state
        .update_context(args.span_id, |ctx| ctx.with_cleared_baggage())
        .is_none()
    {
        debug!("remove_all_baggage: span {} NOT found", args.span_id);
    }
}
