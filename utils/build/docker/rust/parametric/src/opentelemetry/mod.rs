mod dto;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use opentelemetry::{
    trace::{Link, Span, TraceContextExt, Tracer},
    Context, KeyValue,
};

use tracing::debug;

use crate::{get_tracer, opentelemetry::dto::*, AppState};

pub fn app() -> Router<AppState> {
    Router::new()
        .route("/start_span", post(start_span))
        .route("/current_span", get(current_span))
        .route("/span_context", post(get_span_context))
        .route("/is_recording", post(is_recording))
        .route("/set_name", post(set_name))
        .route("/set_status", post(set_status))
        .route("/set_attributes", post(set_attributes))
        .route("/add_event", post(add_event))
        .route("/record_exception", post(record_exception))
        .route("/end_span", post(end_span))
        .route("/flush", post(flush))
    // .route("/set_baggage", post(set_baggage))
    // .route("/otel_set_baggage", post(otel_set_baggage))
    // .route("/get_baggage", get(get_baggage))
    // .route("/get_all_baggage", get(get_all_baggage))
    // .route("/remove_baggage", post(remove_baggage))
    // .route("/remove_all_baggage", post(remove_all_baggage))
}

// Handler implementations

async fn start_span(
    State(state): State<AppState>,
    Json(args): Json<StartSpanArgs>,
) -> Json<StartSpanResult> {
    let mut builder = get_tracer().span_builder(args.name.clone());

    if let Some(kind) = args.span_kind {
        if let Some(kind) = parse_span_kind(kind) {
            builder = builder.with_kind(kind);
        }
    }
    if let Some(timestamp) = args.timestamp {
        builder = builder.with_start_time(system_time_from_millis(timestamp));
    }
    if let Some(links) = args.links {
        let mut valid_links = vec![];
        for link in links {
            if let Some(ctx) = state.contexts.lock().unwrap().get(&link.parent_id) {
                let span = ctx.span();
                if span.span_context().is_valid() {
                    let attributes = parse_attributes(link.attributes.as_ref());
                    valid_links.push(Link::new(span.span_context().clone(), attributes, 0));
                }
            } else {
                return Json(StartSpanResult::error());
            }
        }
        if !valid_links.is_empty() {
            builder = builder.with_links(valid_links);
        }
    }

    // hack to prevent libdatadog from dropping trace chunks
    let mut attributes = vec![opentelemetry::KeyValue::new("_dd.top_level".to_string(), 1)];
    attributes.append(&mut parse_attributes(args.attributes.as_ref()));
    builder = builder.with_attributes(attributes);

    let parent_ctx = if let Some(parent_id) = args.parent_id {
        let spans = state.contexts.lock().unwrap();
        if let Some(ctx) = spans.get(&parent_id) {
            let parent_span = ctx.span();
            debug!("build with otel span {parent_id:?} found");

            let parent =
                Context::new().with_remote_span_context(parent_span.span_context().clone());

            let parent_span_id =
                u64::from_be_bytes(parent.span().span_context().span_id().to_bytes());
            debug!(
                "build with otel span child {}, hex: {}",
                parent_span_id,
                parent.span().span_context().span_id(),
            );
            Some(parent)
        } else {
            debug!("build with otel span {parent_id:?} NOT found");
            None
        }
    } else {
        None
    };

    let span = if let Some(parent_ctx) = parent_ctx {
        builder.start_with_context(get_tracer(), &parent_ctx)
    } else {
        builder.start(get_tracer())
    };

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

    Json(StartSpanResult { span_id, trace_id })
}

async fn current_span(State(state): State<AppState>) -> Json<StartSpanResult> {
    let contexts = state.contexts.lock().unwrap();
    contexts
        .iter()
        .for_each(|(span_id, _)| debug!("otel current_span AppState span_id: {span_id}"));

    let ctx = state.current_context.lock().unwrap();
    let span = ctx.span();
    let span_id = u64::from_be_bytes(span.span_context().span_id().to_bytes());
    let trace_id = u64::from_be_bytes(
        span.span_context().trace_id().to_bytes()[8..16]
            .try_into()
            .unwrap(),
    );

    debug!("current_span otel {span_id} ");

    Json(StartSpanResult { span_id, trace_id })
}

async fn get_span_context(
    State(state): State<AppState>,
    Json(args): Json<SpanContextArgs>,
) -> Json<SpanContextResult> {
    let result = if let Some(ctx) = state.contexts.lock().unwrap().get(&args.span_id) {
        let span = ctx.span();
        let span_context = span.span_context();
        debug!(
            "get_span_context span found: {}, hex: {}",
            args.span_id,
            span_context.span_id().to_string()
        );
        SpanContextResult {
            span_id: span_context.span_id().to_string(),
            trace_id: span_context.trace_id().to_string(),
            trace_flags: Some(if span_context.trace_flags().to_u8() == 1 {
                "01".to_string()
            } else {
                "00".to_string()
            }),
            trace_state: Some(span_context.trace_state().header().to_string()),
            remote: Some(span_context.is_remote()),
        }
    } else {
        let span_id = args.span_id;
        debug!("get_span_context span NOT found: {span_id}");
        SpanContextResult {
            span_id: "0000000000000000".to_string(),
            trace_id: "00000000000000000000000000000000".to_string(),
            trace_flags: Some("00".to_string()),
            trace_state: Some("".to_string()),
            remote: Some(false),
        }
    };

    Json(result)
}

async fn is_recording(
    State(state): State<AppState>,
    Json(args): Json<IsRecordingArgs>,
) -> Json<IsRecordingResult> {
    let recording = if let Some(ctx) = state.contexts.lock().unwrap().get(&args.span_id) {
        let span = ctx.span();
        debug!("is_recording span found: {}", args.span_id);
        span.is_recording()
    } else {
        debug!("is_recording span NOT found: {}", args.span_id);
        false
    };
    Json(IsRecordingResult {
        is_recording: recording,
    })
}

async fn set_name(State(state): State<AppState>, Json(args): Json<SetNameArgs>) {
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&args.span_id) {
        let span = ctx.span();
        debug!("set_name span found: {}", args.span_id);
        span.update_name(args.name);
    } else {
        debug!("set_name span NOT found: {}", args.span_id);
    }
}

async fn set_status(State(state): State<AppState>, Json(args): Json<SetStatusArgs>) {
    let span_id = args.span_id;
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&span_id) {
        let span = ctx.span();
        debug!("set_status span found: {span_id}");
        span.set_status(parse_status(args.code, args.description));
    } else {
        debug!("set_status: span {span_id:?} NOT found");
    }
}

async fn set_attributes(State(state): State<AppState>, Json(args): Json<SetAttributesArgs>) {
    let span_id = args.span_id;
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&span_id) {
        let span = ctx.span();
        debug!("set_attributes span found: {span_id}");
        span.set_attributes(parse_attributes(args.attributes.as_ref()));
    } else {
        debug!("set_attributes: span {span_id:?} NOT found");
    }
}

async fn add_event(State(state): State<AppState>, Json(args): Json<AddEventArgs>) {
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&args.span_id) {
        let span = ctx.span();
        if let Some(timestamp) = args.timestamp {
            span.add_event_with_timestamp(
                args.name,
                system_time_from_millis(timestamp),
                parse_attributes(args.attributes.as_ref()),
            );
        } else {
            span.add_event(args.name, parse_attributes(args.attributes.as_ref()));
        }
    }
}

async fn record_exception(State(state): State<AppState>, Json(args): Json<RecordExceptionArgs>) {
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&args.span_id) {
        let span = ctx.span();
        if span.is_recording() {
            let mut attributes = vec![KeyValue::new("exception.message", args.message)];
            attributes.append(&mut parse_attributes(args.attributes.as_ref()));
            span.add_event("exception", attributes);
            span.set_status(parse_status(2, None));
        }
    }
}

async fn end_span(State(state): State<AppState>, Json(args): Json<EndSpanArgs>) {
    let span_id = args.id;
    let clear = if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&span_id) {
        let span = ctx.span();
        debug!("end_span: span {span_id:?} found");
        if let Some(timestamp) = args.timestamp {
            span.end_with_timestamp(system_time_from_millis(timestamp));
        } else {
            span.end();
        }
        true
    } else {
        debug!("end_span: span {span_id:?} NOT found");
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

async fn flush(State(state): State<AppState>, Json(_args): Json<FlushArgs>) -> Json<FlushResult> {
    let result = state.tracer_provider.force_flush();

    state.contexts.lock().unwrap().clear();

    Json(FlushResult {
        success: result.is_ok(),
    })
}

// async fn set_baggage(State(state): State<AppState>, Json(args): Json<SetBaggageArgs>) {
//     let mut baggage = state.baggage.lock().unwrap();
//     baggage.set(args.key, args.value);
// }

// /// FIXME
// async fn otel_set_baggage(State(state): State<AppState>, Json(args): Json<SetBaggageArgs>) {
//     let mut baggage = state.baggage.lock().unwrap();
//     baggage.set(args.key, args.value);
// }

// async fn get_baggage(
//     State(state): State<AppState>,
//     Json(args): Json<GetBaggageArgs>,
// ) -> Json<GetBaggageResult> {
//     let baggage = state.baggage.lock().unwrap();
//     Json(GetBaggageResult {
//         value: baggage.get_entry_value(&args.key),
//     })
// }

// async fn get_all_baggage(State(state): State<AppState>) -> Json<GetAllBaggageResult> {
//     let baggage = state.baggage.lock().unwrap();
//     Json(GetAllBaggageResult {
//         baggage: Some(baggage.all()),
//     })
// }

// async fn remove_baggage(State(state): State<AppState>, Json(args): Json<RemoveBaggageArgs>) {
//     let mut baggage = state.baggage.lock().unwrap();
//     baggage.remove(&args.key);
// }

// async fn remove_all_baggage(State(state): State<AppState>) {
//     let mut baggage = state.baggage.lock().unwrap();
//     baggage.clear();
// }
