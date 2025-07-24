mod dto;

use axum::{
    extract::{Json, State},
    http::{HeaderMap, HeaderName},
    routing::{get, post},
    Router,
};
use dto::*;
use opentelemetry::{
    trace::{Span, TraceContextExt, Tracer},
    Context,
};
use opentelemetry_http::HeaderExtractor;
use std::{collections::HashMap, vec};
use tracing::debug;

use crate::{get_tracer, AppState};

pub fn app() -> Router<AppState> {
    Router::new()
        .route("/span/start", post(start_span))
        .route("/span/current", get(current_span))
        .route("/span/finish", post(finish_span))
        .route("/span/set_resource", post(set_resource))
        .route("/span/set_meta", post(set_meta))
        .route("/span/set_metric", post(set_metric))
        .route("/span/error", post(set_error))
        .route("/span/inject_headers", post(inject_headers))
        .route("/span/extract_headers", post(extract_headers))
        .route("/span/flush", post(flush_spans))
    // .route("/span/set_baggage", post(set_baggage))
    // .route("/span/get_baggage", get(get_baggage))
    // .route("/span/get_all_baggage", get(get_all_baggage))
    // .route("/span/remove_baggage", post(remove_baggage))
    // .route("/span/remove_all_baggage", post(remove_all_baggage))
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

    // hack to prevent libdatadog from dropping trace chunks
    attributes.push(opentelemetry::KeyValue::new("_dd.top_level", 1));

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
            let parent_span = parent_ctx.span();
            debug!("build with span {parent_id:?} found");

            let parent =
                Context::new().with_remote_span_context(parent_span.span_context().clone());

            let parent_span_id =
                u64::from_be_bytes(parent.span().span_context().span_id().to_bytes());
            debug!(
                "build with span child {}, hex: {}",
                parent_span_id,
                parent.span().span_context().span_id(),
            );

            debug!("build with span child {:#?}", parent.span());

            Some(parent)
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

    let span = if let Some(parent_ctx) = parent_ctx {
        state
            .current_context
            .lock()
            .unwrap()
            .clone_from(&parent_ctx);
        builder.start_with_context(get_tracer(), &parent_ctx)
    } else {
        state
            .current_context
            .lock()
            .unwrap()
            .clone_from(&Context::current());
        builder.start(get_tracer())
    };

    let id = span.span_context().span_id();
    let span_id = u64::from_be_bytes(id.to_bytes());
    let trace_id = u128::from_be_bytes(span.span_context().trace_id().to_bytes());

    let ctx = Context::current_with_span(span);

    state.contexts.lock().unwrap().insert(span_id, ctx);

    debug!("created span {span_id} ");

    Json(StartSpanResult { span_id, trace_id })
}

async fn current_span(State(state): State<AppState>) -> Json<StartSpanResult> {
    let contexts = state.contexts.lock().unwrap();
    contexts
        .iter()
        .for_each(|(span_id, _)| debug!("current_span AppState span_id: {span_id}"));

    let ctx = state.current_context.lock().unwrap();
    let span = ctx.span();
    let span_id = u64::from_be_bytes(span.span_context().span_id().to_bytes());
    let trace_id = u128::from_be_bytes(span.span_context().trace_id().to_bytes());

    debug!("current_span {span_id} ");

    Json(StartSpanResult { span_id, trace_id })
}

async fn finish_span(State(state): State<AppState>, Json(args): Json<SpanFinishArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    let clear = if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.span();
        span.end();
        debug!("finish_span: span {} found", args.span_id);
        true
    } else {
        debug!("finish_span: span {} NOT found", args.span_id);
        false
    };

    if clear {
        state
            .current_context
            .lock()
            .unwrap()
            .clone_from(&Context::current());
    }
}

async fn set_resource(State(state): State<AppState>, Json(args): Json<SpanSetResourceArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.span();
        debug!("set_resource: span {} found", args.span_id);
        span.set_attribute(opentelemetry::KeyValue::new(
            "resource".to_string(),
            args.resource.clone(),
        ));
    } else {
        debug!("set_resource: span {} NOT found", args.span_id);
    }
}

async fn set_meta(State(state): State<AppState>, Json(args): Json<SpanSetMetaArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.span();
        debug!("set_meta: span {} found", args.span_id);
        span.set_attribute(opentelemetry::KeyValue::new(
            args.key.clone(),
            args.value.clone(),
        ));
    } else {
        debug!("set_meta: span {} NOT found", args.span_id);
    }
}

async fn set_metric(State(state): State<AppState>, Json(args): Json<SpanSetMetricArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.span();
        debug!("set_metric: span {} found", args.span_id);
        span.set_attribute(opentelemetry::KeyValue::new(
            args.key.clone(),
            args.value.to_string(),
        ));
    } else {
        debug!("set_metric: span {} NOT found", args.span_id);
    }
}

async fn set_error(State(state): State<AppState>, Json(args): Json<SpanErrorArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get_mut(&args.span_id) {
        let span = ctx.span();
        debug!("set_error: span {} found", args.span_id);
        span.set_attribute(opentelemetry::KeyValue::new(
            "error".to_string(),
            "true".to_string(),
        ));
        span.set_attribute(opentelemetry::KeyValue::new(
            "error.type".to_string(),
            args.r#type.clone(),
        ));
        span.set_attribute(opentelemetry::KeyValue::new(
            "error.msg".to_string(),
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

async fn inject_headers(
    State(state): State<AppState>,
    Json(args): Json<SpanInjectHeadersArgs>,
) -> Json<SpanInjectHeadersResult> {
    let contexts = state.contexts.lock().unwrap();
    if let Some(ctx) = contexts.get(&args.span_id) {
        let span = ctx.span();
        opentelemetry::global::get_text_map_propagator(|propagator| {
            let mut injector = HashMap::new();

            // TODO: review!
            let context = Context::new().with_remote_span_context(span.span_context().clone());

            debug!("inject_headers: context: {:#?}", context);

            propagator.inject_context(&context, &mut injector);

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
        let extractor = args
            .http_headers
            .iter()
            .fold(HeaderMap::new(), |mut map, kv| {
                map.append(
                    kv.key.as_str().parse::<HeaderName>().unwrap(),
                    kv.value.parse().unwrap(),
                );
                map
            });

        debug!("extract_headers: received {:#?}", extractor);

        let context = propagator.extract(&HeaderExtractor(&extractor));

        if !context.span().span_context().is_valid() {
            debug!("extract_headers: no valid context. Returning empty result");
            return Json(SpanExtractHeadersResult { span_id: None });
        }

        let span_id = u64::from_be_bytes(context.span().span_context().span_id().to_bytes());
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

async fn flush_spans(State(state): State<AppState>) {
    let result = state.tracer_provider.force_flush();
    state.contexts.lock().unwrap().clear();
    state.extracted_span_contexts.lock().unwrap().clear();
    state
        .current_context
        .lock()
        .unwrap()
        .clone_from(&Context::current());
    debug!(
        "flush_spans: all spans and contexts cleared ok: {}",
        result.is_ok()
    );
}

/*
async fn set_baggage(State(state): State<AppState>, Json(args): Json<SpanSetBaggageArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(span) = spans.get_mut(&args.span_id) {
        debug!("set_baggage: span {} found", args.span_id);
        span.set_baggage_item(args.key.clone(), Some(args.value.clone()));
    } else {
        debug!("set_baggage: span {} NOT found", args.span_id);
    }
}

async fn get_baggage(
    State(state): State<AppState>,
    Json(args): Json<SpanGetBaggageArgs>,
) -> Json<SpanGetBaggageResult> {
    let contexts = state.contexts.lock().unwrap();
    if let Some(span) = spans.get(&args.span_id) {
        debug!("get_baggage: span {} found", args.span_id);
        Json(SpanGetBaggageResult {
            baggage: span.get_baggage_item(&args.key),
        })
    } else {
        debug!("get_baggage: span {} NOT found", args.span_id);
        Json(SpanGetBaggageResult { baggage: None })
    }
}

async fn get_all_baggage(
    State(state): State<AppState>,
    Json(args): Json<SpanGetAllBaggageArgs>,
) -> Json<SpanGetAllBaggageResult> {
    let contexts = state.contexts.lock().unwrap();
    if let Some(span) = spans.get(&args.span_id) {
        debug!("get_all_baggage: span {} found", args.span_id);
        Json(SpanGetAllBaggageResult {
            baggage: Some(span.baggage.clone()),
        })
    } else {
        debug!("get_all_baggage: span {} NOT found", args.span_id);
        Json(SpanGetAllBaggageResult { baggage: None })
    }
}

async fn remove_baggage(State(state): State<AppState>, Json(args): Json<SpanRemoveBaggageArgs>) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(span) = spans.get_mut(&args.span_id) {
        debug!("remove_baggage: span {} found", args.span_id);
        span.set_baggage_item(args.key.clone(), None);
    } else {
        debug!("remove_baggage: span {} NOT found", args.span_id);
    }
}

async fn remove_all_baggage(
    State(state): State<AppState>,
    Json(args): Json<SpanRemoveAllBaggageArgs>,
) {
    let mut contexts = state.contexts.lock().unwrap();
    if let Some(span) = spans.get_mut(&args.span_id) {
        debug!("remove_all_baggage: span {} found", args.span_id);
        span.baggage.clear();
    } else {
        debug!("remove_all_baggage: span {} NOT found", args.span_id);
    }
}
*/
