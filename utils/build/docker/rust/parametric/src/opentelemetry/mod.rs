mod dto;

use std::sync::Arc;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use opentelemetry::{
    global,
    metrics::{Counter, Gauge, Histogram, Meter, MeterProvider, ObservableCounter, ObservableGauge, ObservableUpDownCounter, UpDownCounter},
    trace::{Link, Span, TraceContextExt, Tracer},
    Context, InstrumentationScope, KeyValue,
};

use tracing::debug;

use crate::{get_tracer, opentelemetry::dto::*, AppState, ContextWithParent};

pub enum MeterInstrument {
    Counter(Counter<u64>),
    UpDownCounter(UpDownCounter<i64>),
    Gauge(Gauge<f64>),
    Histogram(Histogram<f64>),
    ObservableCounter(ObservableCounter<u64>),
    ObservableUpDownCounter(ObservableUpDownCounter<i64>),
    ObservableGauge(ObservableGauge<f64>),
}

pub fn app() -> Router<AppState> {
    Router::new()
        .route("/trace/otel/start_span", post(start_span))
        .route("/trace/otel/current_span", get(current_span))
        .route("/trace/otel/span_context", post(get_span_context))
        .route("/trace/otel/is_recording", post(is_recording))
        .route("/trace/otel/set_name", post(set_name))
        .route("/trace/otel/set_status", post(set_status))
        .route("/trace/otel/set_attributes", post(set_attributes))
        .route("/trace/otel/add_event", post(add_event))
        .route("/trace/otel/record_exception", post(record_exception))
        .route("/trace/otel/end_span", post(end_span))
        .route("/trace/otel/flush", post(flush))
        .route("/metrics/otel/get_meter", post(otel_get_meter))
        .route("/metrics/otel/create_counter", post(otel_create_counter))
        .route("/metrics/otel/counter_add", post(otel_counter_add))
        .route("/metrics/otel/create_updowncounter", post(otel_create_updowncounter))
        .route("/metrics/otel/updowncounter_add", post(otel_updowncounter_add))
        .route("/metrics/otel/create_gauge", post(otel_create_gauge))
        .route("/metrics/otel/gauge_record", post(otel_gauge_record))
        .route("/metrics/otel/create_histogram", post(otel_create_histogram))
        .route("/metrics/otel/histogram_record", post(otel_histogram_record))
        .route("/metrics/otel/create_asynchronous_counter", post(otel_create_asynchronous_counter))
        .route("/metrics/otel/create_asynchronous_updowncounter", post(otel_create_asynchronous_updowncounter))
        .route("/metrics/otel/create_asynchronous_gauge", post(otel_create_asynchronous_gauge))
        .route("/metrics/otel/force_flush", post(otel_metrics_force_flush))
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
        builder = builder.with_start_time(system_time_from_micros(timestamp));
    }
    if let Some(links) = args.links {
        let mut valid_links = vec![];
        for link in links {
            if let Some(ctx) = state.contexts.lock().unwrap().get(&link.parent_id) {
                let span = ctx.context.span();
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

    // TODO: review!
    let mut attributes = vec![
        // hack to prevent libdatadog from dropping trace chunks
        opentelemetry::KeyValue::new("_dd.top_level".to_string(), 1),
        // hack to fix some test_otel_span_methods.py with wrong resorce name
        opentelemetry::KeyValue::new("resource.name".to_string(), args.name),
    ];
    attributes.append(&mut parse_attributes(args.attributes.as_ref()));
    builder = builder.with_attributes(attributes);

    let parent_ctx = if let Some(parent_id) = args.parent_id {
        let spans = state.contexts.lock().unwrap();
        if let Some(ctx) = spans.get(&parent_id) {
            let parent_span = ctx.context.span();
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

    let span = if let Some(ref parent_ctx) = parent_ctx {
        builder.start_with_context(get_tracer(), parent_ctx)
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
    let ctx_with_parent = Arc::new(ContextWithParent::new(ctx, parent_ctx));
    *state.current_context.lock().unwrap() = ctx_with_parent.clone();
    state
        .contexts
        .lock()
        .unwrap()
        .insert(span_id, ctx_with_parent.clone());

    debug!("created otel span {span_id}");

    Json(StartSpanResult { span_id, trace_id })
}

async fn current_span(State(state): State<AppState>) -> Json<StartSpanResult> {
    let contexts = state.contexts.lock().unwrap();
    contexts
        .iter()
        .for_each(|(span_id, _)| debug!("otel current_span AppState span_id: {span_id}"));

    let ctx = state.current_context.lock().unwrap();
    let span = ctx.context.span();
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
        let span = ctx.context.span();
        let span_context = span.span_context();
        debug!(
            "get_span_context span found: {}, hex: {}",
            args.span_id,
            span_context.span_id().to_string()
        );
        SpanContextResult {
            span_id: span_context.span_id().to_string(),
            trace_id: span_context.trace_id().to_string(),
            trace_flags: Some(format!("{:02x}", span_context.trace_flags().to_u8())),
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
        let span = ctx.context.span();
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
        let span = ctx.context.span();
        debug!("set_name span found: {}", args.span_id);
        span.update_name(args.name.clone());

        // TODO: is this ok? see Test_Parametric_OtelSpan_Set_Name
        span.set_attribute(opentelemetry::KeyValue::new("resource.name", args.name));
    } else {
        debug!("set_name span NOT found: {}", args.span_id);
    }
}

async fn set_status(State(state): State<AppState>, Json(args): Json<SetStatusArgs>) {
    let span_id = args.span_id;
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&span_id) {
        let span = ctx.context.span();
        debug!("set_status span found: {span_id}");
        span.set_status(parse_status(args.code, args.description));
    } else {
        debug!("set_status: span {span_id:?} NOT found");
    }
}

async fn set_attributes(State(state): State<AppState>, Json(args): Json<SetAttributesArgs>) {
    let span_id = args.span_id;
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&span_id) {
        let span = ctx.context.span();
        let attributes = parse_attributes(args.attributes.as_ref());
        debug!("set_attributes span found: {span_id} {attributes:#?}");
        span.set_attributes(attributes);
    } else {
        debug!("set_attributes: span {span_id:?} NOT found");
    }
}

async fn add_event(State(state): State<AppState>, Json(args): Json<AddEventArgs>) {
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&args.span_id) {
        let span = ctx.context.span();
        if let Some(timestamp) = args.timestamp {
            span.add_event_with_timestamp(
                args.name,
                system_time_from_micros(timestamp),
                parse_attributes(args.attributes.as_ref()),
            );
        } else {
            span.add_event(args.name, parse_attributes(args.attributes.as_ref()));
        }
    }
}

async fn record_exception(State(state): State<AppState>, Json(args): Json<RecordExceptionArgs>) {
    if let Some(ctx) = state.contexts.lock().unwrap().get_mut(&args.span_id) {
        let span = ctx.context.span();
        if span.is_recording() {
            let mut attributes = vec![
                KeyValue::new("exception.message", args.message),
                KeyValue::new("exception.type", "panic"), // no exception type in rust
            ];
            attributes.append(&mut parse_attributes(args.attributes.as_ref()));
            span.add_event("exception", attributes);
        }
    }
}

async fn end_span(State(state): State<AppState>, Json(args): Json<EndSpanArgs>) {
    let span_id = args.id;
    let mut contexts = state.contexts.lock().unwrap();
    let parent = if let Some(ctx) = contexts.get_mut(&span_id) {
        let span = ctx.context.span();
        debug!("end_span: span {span_id:?} found");
        if let Some(timestamp) = args.timestamp {
            span.end_with_timestamp(system_time_from_micros(timestamp));
        } else {
            span.end();
        }
        ctx.parent.clone()
    } else {
        debug!("end_span: span {span_id:?} NOT found");
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

async fn flush(State(state): State<AppState>, Json(_args): Json<FlushArgs>) -> Json<FlushResult> {
    let result = state.tracer_provider.force_flush();

    state.contexts.lock().unwrap().clear();
    state.extracted_span_contexts.lock().unwrap().clear();
    *state.current_context.lock().unwrap() = Arc::new(ContextWithParent::default());

    debug!(
        "otel_flush: all spans and contexts cleared ok: {:?}",
        result
    );

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

// --- Metrics Handlers ---

fn create_instrument_key(
    meter_name: &str,
    name: &str,
    kind: &str,
    unit: &str,
    description: &str,
) -> String {
    format!("{meter_name}::{name}::{kind}::{unit}::{description}")
}

async fn otel_get_meter(
    State(state): State<AppState>,
    Json(args): Json<OtelGetMeterArgs>,
) -> Json<OtelGetMeterReturn> {
    let mut meters = state.otel_meters.lock().unwrap();
    // Store meters by name only, matching the behavior of other language implementations
    if !meters.contains_key(&args.name) {
        // Use global meter provider configured by init_metrics(), matching Python's get_meter_provider() behavior
        let meter_provider = global::meter_provider();
        let name_static: &'static str = Box::leak(args.name.clone().into_boxed_str());

        // Create InstrumentationScope with name, version, and schema_url
        // Let the SDK handle attributes internally - no custom parsing needed
        let mut scope_builder = InstrumentationScope::builder(name_static);
        if let Some(version) = args.version.as_ref() {
            scope_builder = scope_builder.with_version(version.clone());
        }
        if let Some(schema_url) = args.schema_url.as_ref() {
            scope_builder = scope_builder.with_schema_url(schema_url.clone());
        }
        // Note: attributes are handled by the SDK internally, similar to Python's get_meter()
        let scope = scope_builder.build();

        // Use meter_with_scope() to include version and schema_url
        let meter = meter_provider.meter_with_scope(scope);
        meters.insert(args.name.clone(), meter);
    }
    Json(OtelGetMeterReturn {})
}

async fn otel_create_counter(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateCounterArgs>,
) -> Json<OtelCreateCounterReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let counter = meter
        .u64_counter(args.name.clone())
        .with_unit(args.unit.clone())
        .with_description(args.description.clone())
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "counter",
        &args.unit,
        &args.description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::Counter(counter));

    Json(OtelCreateCounterReturn {})
}

async fn otel_counter_add(
    State(state): State<AppState>,
    Json(args): Json<OtelCounterAddArgs>,
) -> Json<OtelCounterAddReturn> {
    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "counter",
        &args.unit,
        &args.description,
    );

    let instruments = state.otel_meter_instruments.lock().unwrap();
    let instrument = instruments
        .get(&instrument_key)
        .expect("Instrument not found in registered instruments");

    if let MeterInstrument::Counter(counter) = instrument {
        let value = args.value.as_u64().unwrap_or(0);
        let attributes = parse_attributes(Some(&args.attributes));
        counter.add(value, &attributes);
    }

    Json(OtelCounterAddReturn {})
}

async fn otel_create_updowncounter(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateUpDownCounterArgs>,
) -> Json<OtelCreateUpDownCounterReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let counter = meter
        .i64_up_down_counter(args.name.clone())
        .with_unit(args.unit.clone())
        .with_description(args.description.clone())
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "updowncounter",
        &args.unit,
        &args.description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::UpDownCounter(counter));

    Json(OtelCreateUpDownCounterReturn {})
}

async fn otel_updowncounter_add(
    State(state): State<AppState>,
    Json(args): Json<OtelUpDownCounterAddArgs>,
) -> Json<OtelUpDownCounterAddReturn> {
    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "updowncounter",
        &args.unit,
        &args.description,
    );

    let instruments = state.otel_meter_instruments.lock().unwrap();
    let instrument = instruments
        .get(&instrument_key)
        .expect("Instrument not found in registered instruments");

    if let MeterInstrument::UpDownCounter(counter) = instrument {
        let value = args.value.as_i64().unwrap_or(0);
        let attributes = parse_attributes(Some(&args.attributes));
        counter.add(value, &attributes);
    }

    Json(OtelUpDownCounterAddReturn {})
}

async fn otel_create_gauge(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateGaugeArgs>,
) -> Json<OtelCreateGaugeReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let gauge = meter
        .f64_gauge(args.name.clone())
        .with_unit(args.unit.clone())
        .with_description(args.description.clone())
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "gauge",
        &args.unit,
        &args.description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::Gauge(gauge));

    Json(OtelCreateGaugeReturn {})
}

async fn otel_gauge_record(
    State(state): State<AppState>,
    Json(args): Json<OtelGaugeRecordArgs>,
) -> Json<OtelGaugeRecordReturn> {
    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "gauge",
        &args.unit,
        &args.description,
    );

    let instruments = state.otel_meter_instruments.lock().unwrap();
    let instrument = instruments
        .get(&instrument_key)
        .expect("Instrument not found in registered instruments");

    if let MeterInstrument::Gauge(gauge) = instrument {
        let value = args.value.as_f64().unwrap_or(0.0);
        let attributes = parse_attributes(Some(&args.attributes));
        gauge.record(value, &attributes);
    }

    Json(OtelGaugeRecordReturn {})
}

async fn otel_create_histogram(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateHistogramArgs>,
) -> Json<OtelCreateHistogramReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let histogram = meter
        .f64_histogram(args.name.clone())
        .with_unit(args.unit.clone())
        .with_description(args.description.clone())
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "histogram",
        &args.unit,
        &args.description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::Histogram(histogram));

    Json(OtelCreateHistogramReturn {})
}

async fn otel_histogram_record(
    State(state): State<AppState>,
    Json(args): Json<OtelHistogramRecordArgs>,
) -> Json<OtelHistogramRecordReturn> {
    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "histogram",
        &args.unit,
        &args.description,
    );

    let instruments = state.otel_meter_instruments.lock().unwrap();
    let instrument = instruments
        .get(&instrument_key)
        .expect("Instrument not found in registered instruments");

    if let MeterInstrument::Histogram(histogram) = instrument {
        let value = args.value.as_f64().unwrap_or(0.0);
        let attributes = parse_attributes(Some(&args.attributes));
        histogram.record(value, &attributes);
    }

    Json(OtelHistogramRecordReturn {})
}

async fn otel_create_asynchronous_counter(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateAsynchronousCounterArgs>,
) -> Json<OtelCreateAsynchronousCounterReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let value = args.value.as_u64().unwrap_or(0);
    let attributes = parse_attributes(Some(&args.attributes));
    let name = args.name.clone();
    let unit = args.unit.clone();
    let description = args.description.clone();

    let observable_counter = meter
        .u64_observable_counter(name)
        .with_unit(unit.clone())
        .with_description(description.clone())
        .with_callback(move |observer| {
            observer.observe(value, &attributes);
        })
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "observable_counter",
        &unit,
        &description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::ObservableCounter(observable_counter));

    Json(OtelCreateAsynchronousCounterReturn {})
}

async fn otel_create_asynchronous_updowncounter(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateAsynchronousUpDownCounterArgs>,
) -> Json<OtelCreateAsynchronousUpDownCounterReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let value = args.value.as_i64().unwrap_or(0);
    let attributes = parse_attributes(Some(&args.attributes));
    let name = args.name.clone();
    let unit = args.unit.clone();
    let description = args.description.clone();

    let observable_updowncounter = meter
        .i64_observable_up_down_counter(name)
        .with_unit(unit.clone())
        .with_description(description.clone())
        .with_callback(move |observer| {
            observer.observe(value, &attributes);
        })
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "observable_updowncounter",
        &unit,
        &description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::ObservableUpDownCounter(observable_updowncounter));

    Json(OtelCreateAsynchronousUpDownCounterReturn {})
}

async fn otel_create_asynchronous_gauge(
    State(state): State<AppState>,
    Json(args): Json<OtelCreateAsynchronousGaugeArgs>,
) -> Json<OtelCreateAsynchronousGaugeReturn> {
    let meters = state.otel_meters.lock().unwrap();
    let meter = meters
        .get(&args.meter_name)
        .expect("Meter not found in registered meters");

    let value = args.value.as_f64().unwrap_or(0.0);
    let attributes = parse_attributes(Some(&args.attributes));
    let name = args.name.clone();
    let unit = args.unit.clone();
    let description = args.description.clone();

    let observable_gauge = meter
        .f64_observable_gauge(name)
        .with_unit(unit.clone())
        .with_description(description.clone())
        .with_callback(move |observer| {
            observer.observe(value, &attributes);
        })
        .build();

    let instrument_key = create_instrument_key(
        &args.meter_name,
        &args.name,
        "observable_gauge",
        &unit,
        &description,
    );
    state
        .otel_meter_instruments
        .lock()
        .unwrap()
        .insert(instrument_key, MeterInstrument::ObservableGauge(observable_gauge));

    Json(OtelCreateAsynchronousGaugeReturn {})
}

async fn otel_metrics_force_flush(
    State(state): State<AppState>,
    Json(_args): Json<OtelMetricsForceFlushArgs>,
) -> Json<OtelMetricsForceFlushReturn> {
    let meter_provider_guard = state.meter_provider.lock().unwrap();
    let result = if let Some(meter_provider) = meter_provider_guard.as_ref() {
        meter_provider.force_flush().is_ok()
    } else {
        false
    };
    Json(OtelMetricsForceFlushReturn { success: result })
}
