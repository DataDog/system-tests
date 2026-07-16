use std::{
    collections::HashMap,
    net::SocketAddr,
    time::{Duration, SystemTime},
};

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, Method, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, options, post},
    Json, Router,
};
use opentelemetry::{
    baggage::BaggageExt,
    global,
    propagation::TextMapPropagator,
    trace::{Span, SpanKind, Status, TraceContextExt, Tracer},
    Context, KeyValue,
};
use opentelemetry_http::{HeaderExtractor, HeaderInjector};
use opentelemetry_sdk::trace::SdkTracerProvider;
use reqwest_middleware::ClientBuilder;
use reqwest_tracing::TracingMiddleware;
use serde::Deserialize;
use tracing_opentelemetry::OpenTelemetrySpanExt;

use integration::DatadogClientSpanBackend;

mod integration;

const VERSION_FILE: &str = "/app/SYSTEM_TESTS_LIBRARY_VERSION";
const DOWNSTREAM_RETURN_HEADERS_URL: &str = "http://localhost:7777/returnheaders";

#[derive(Clone)]
struct AppState {
    tracer_provider: SdkTracerProvider,
    downstream_url: String,
}

#[derive(Deserialize)]
struct StatusQuery {
    code: u16,
}

#[derive(Deserialize)]
struct SpansQuery {
    repeats: Option<String>,
    garbage: Option<String>,
}

#[derive(Deserialize)]
struct StatsUniqueQuery {
    code: Option<String>,
}

#[derive(Deserialize)]
struct E2eSpanQuery {
    #[serde(rename = "parentName")]
    parent_name: Option<String>,
    #[serde(rename = "childName")]
    child_name: Option<String>,
    #[serde(rename = "shouldIndex")]
    should_index: Option<String>,
}

#[tokio::main]
async fn main() {
    let tracer_provider = integration::install_datadog_tracing();

    let app = app(AppState {
        tracer_provider: tracer_provider.clone(),
        downstream_url: DOWNSTREAM_RETURN_HEADERS_URL.to_owned(),
    })
    .into_make_service_with_connect_info::<SocketAddr>();

    let listener = tokio::net::TcpListener::bind("0.0.0.0:7777").await.unwrap();
    println!("Listening on port 7777");
    axum::serve(listener, app).await.unwrap();

    tracer_provider.shutdown().unwrap();
}

fn app(state: AppState) -> Router {
    let router = Router::new()
        .route("/", get(index))
        .route("/", post(index))
        .route("/", options(index))
        // Basic info endpoints
        .route("/healthcheck", get(healthcheck))
        .route("/headers", get(headers))
        .route("/status", get(status))
        .route("/spans", get(spans))
        .route("/stats-unique", get(stats_unique))
        .route("/params/{value}", get(params))
        .route("/sample_rate_route/{i}", get(sample_rate_route))
        .route("/flush", get(flush))
        .route("/createextraservice", get(create_extra_service))
        .route("/e2e_otel_span", get(e2e_otel_span))
        .route("/e2e_single_span", get(e2e_single_span))
        .route(
            "/otel_drop_in_default_propagator_extract",
            get(otel_drop_in_default_propagator_extract),
        )
        .route(
            "/otel_drop_in_default_propagator_inject",
            get(otel_drop_in_default_propagator_inject),
        )
        .route("/returnheaders", get(returnheaders).post(returnheaders))
        .route(
            "/requestdownstream",
            get(requestdownstream).post(requestdownstream),
        )
        .route("/make_distant_call", get(make_distant_call))
        .with_state(state);
    integration::install_middleware(router)
}

// ─── Basic endpoints ─────────────────────────────────────────────────────────

async fn healthcheck() -> Json<serde_json::Value> {
    let version = std::fs::read_to_string(VERSION_FILE).unwrap_or_else(|_| "unknown".to_string());
    let version = version.trim().to_string();
    Json(serde_json::json!({
        "status": "ok",
        "library": {
            "name": "rust",
            "version": version,
        }
    }))
}

async fn index() -> Response {
    (
        StatusCode::OK,
        [
            (axum::http::header::CONTENT_TYPE, "text/plain"),
            (axum::http::header::CONTENT_LENGTH, "13"),
        ],
        "Hello world!\n",
    )
        .into_response()
}

async fn status(Query(query): Query<StatusQuery>) -> StatusCode {
    StatusCode::from_u16(query.code).unwrap_or(StatusCode::BAD_REQUEST)
}

async fn headers() -> Response {
    (
        StatusCode::OK,
        [
            (axum::http::header::CONTENT_TYPE, "text"),
            (axum::http::header::CONTENT_LANGUAGE, "en-US"),
            (axum::http::header::CONTENT_LENGTH, "15"),
        ],
        "Hello headers!\n",
    )
        .into_response()
}

async fn spans(Query(query): Query<SpansQuery>) -> Response {
    let repeats = match parse_nonnegative(query.repeats.as_deref()) {
        Ok(value) => value,
        Err(status) => return status.into_response(),
    };
    let garbage = match parse_nonnegative(query.garbage.as_deref()) {
        Ok(value) => value,
        Err(status) => return status.into_response(),
    };

    generate_spans(&global::tracer("weblog"), repeats, garbage);
    format!("Generated {repeats} spans with {garbage} garbage tags\n").into_response()
}

fn parse_nonnegative(value: Option<&str>) -> Result<usize, StatusCode> {
    value.map_or(Ok(0), |value| {
        value.parse().map_err(|_| StatusCode::BAD_REQUEST)
    })
}

fn generate_spans<T: Tracer>(tracer: &T, repeats: usize, garbage: usize) {
    for index in 0..repeats {
        let mut span = tracer.start(format!("repeat-{index}"));
        for tag_index in 0..garbage {
            span.set_attribute(KeyValue::new(
                format!("garbage-{tag_index}"),
                tag_index.to_string(),
            ));
        }
        span.end();
    }
}

async fn stats_unique(Query(query): Query<StatsUniqueQuery>) -> StatusCode {
    query
        .code
        .map_or(Ok(StatusCode::OK), |code| {
            code.parse()
                .ok()
                .and_then(|code| StatusCode::from_u16(code).ok())
                .ok_or(StatusCode::BAD_REQUEST)
        })
        .unwrap_or(StatusCode::BAD_REQUEST)
}

async fn params(Path(_value): Path<String>) -> StatusCode {
    StatusCode::OK
}

async fn sample_rate_route(Path(_i): Path<String>) -> StatusCode {
    StatusCode::OK
}

async fn flush(State(state): State<AppState>) -> StatusCode {
    state
        .tracer_provider
        .force_flush()
        .map_or(StatusCode::INTERNAL_SERVER_ERROR, |_| StatusCode::OK)
}

async fn create_extra_service(Query(query): Query<HashMap<String, String>>) -> StatusCode {
    let Some(service_name) = query.get("serviceName") else {
        return StatusCode::BAD_REQUEST;
    };

    Context::current()
        .span()
        .set_attribute(KeyValue::new("service.name", service_name.clone()));
    StatusCode::OK
}

async fn e2e_otel_span(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<E2eSpanQuery>,
) -> StatusCode {
    let Some(parent_name) = query.parent_name else {
        return StatusCode::BAD_REQUEST;
    };
    let Some(child_name) = query.child_name else {
        return StatusCode::BAD_REQUEST;
    };

    let user_agent = user_agent(&headers);
    create_e2e_otel_spans(
        &global::tracer("system-tests"),
        &parent_name,
        &child_name,
        &user_agent,
        query.should_index.as_deref() == Some("1"),
    );
    flush_provider(&state.tracer_provider)
}

fn create_e2e_otel_spans<T: Tracer>(
    tracer: &T,
    parent_name: &str,
    child_name: &str,
    user_agent: &str,
    should_index: bool,
) where
    T::Span: Send + Sync + 'static,
{
    let start = SystemTime::now();
    let mut parent = tracer
        .span_builder(parent_name.to_owned())
        .with_kind(SpanKind::Internal)
        .with_attributes(e2e_span_attributes(
            parent_name,
            user_agent,
            should_index,
            true,
        ))
        .start_with_context(tracer, &Context::new());
    parent.set_status(Status::Error {
        description: "testing_end_span_options".into(),
    });

    let parent_context = Context::new().with_span(parent);
    let mut child = tracer
        .span_builder(child_name.to_owned())
        .with_kind(SpanKind::Internal)
        .with_start_time(start)
        .with_attributes(e2e_span_attributes(
            child_name,
            user_agent,
            should_index,
            false,
        ))
        .start_with_context(tracer, &parent_context);
    child.end_with_timestamp(start + Duration::from_secs(1));
    parent_context.span().end();
}

fn e2e_span_attributes(
    resource_name: &str,
    user_agent: &str,
    should_index: bool,
    is_parent: bool,
) -> Vec<KeyValue> {
    let mut attributes = vec![
        KeyValue::new("resource.name", resource_name.to_owned()),
        KeyValue::new("http.useragent", user_agent.to_owned()),
    ];
    if is_parent {
        attributes.push(KeyValue::new("attributes", "values"));
    }
    if should_index {
        attributes.push(KeyValue::new("_dd.filter.kept", 1i64));
        attributes.push(KeyValue::new("_dd.filter.id", "system_tests_e2e"));
    }
    attributes
}

async fn e2e_single_span(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<E2eSpanQuery>,
) -> StatusCode {
    let Some(parent_name) = query.parent_name else {
        return StatusCode::BAD_REQUEST;
    };
    let Some(child_name) = query.child_name else {
        return StatusCode::BAD_REQUEST;
    };

    create_e2e_single_spans(
        &parent_name,
        &child_name,
        &user_agent(&headers),
        query.should_index.as_deref() == Some("1"),
    );
    flush_provider(&state.tracer_provider)
}

fn create_e2e_single_spans(
    parent_name: &str,
    child_name: &str,
    user_agent: &str,
    should_index: bool,
) {
    let parent = tracing::info_span!(
        parent: None,
        "e2e_single_span",
        otel.name = parent_name,
        otel.kind = "internal"
    );
    parent.set_attribute("http.useragent", user_agent.to_owned());
    if should_index {
        parent.set_attribute("_dd.filter.kept", 1i64);
        parent.set_attribute("_dd.filter.id", "system_tests_e2e");
    }

    let child = tracing::info_span!(
        parent: &parent,
        "e2e_single_span",
        otel.name = child_name,
        otel.kind = "internal"
    );
    child.set_attribute("http.useragent", user_agent.to_owned());
    if should_index {
        child.set_attribute("_dd.filter.kept", 1i64);
        child.set_attribute("_dd.filter.id", "system_tests_e2e");
    }

    drop(child);
    drop(parent);
}

fn flush_provider(provider: &SdkTracerProvider) -> StatusCode {
    provider
        .force_flush()
        .map_or(StatusCode::INTERNAL_SERVER_ERROR, |_| StatusCode::OK)
}

fn user_agent(headers: &HeaderMap) -> String {
    headers
        .get(axum::http::header::USER_AGENT)
        .and_then(|header| header.to_str().ok())
        .unwrap_or_default()
        .to_owned()
}

async fn otel_drop_in_default_propagator_extract(headers: HeaderMap) -> Json<serde_json::Value> {
    global::get_text_map_propagator(|propagator| {
        Json(extract_propagator_context(propagator, &headers))
    })
}

fn extract_propagator_context(
    propagator: &dyn TextMapPropagator,
    headers: &HeaderMap,
) -> serde_json::Value {
    let context = propagator.extract(&HeaderExtractor(headers));
    let span = context.span();
    let span_context = span.span_context();
    let trace_id = u64::from_be_bytes(span_context.trace_id().to_bytes()[8..].try_into().unwrap());
    let span_id = u64::from_be_bytes(span_context.span_id().to_bytes());

    serde_json::json!({
        "trace_id": trace_id,
        "span_id": span_id,
        "tracestate": span_context.trace_state().header(),
        "baggage": context.baggage().to_string(),
    })
}

async fn otel_drop_in_default_propagator_inject() -> Json<HashMap<String, String>> {
    global::get_text_map_propagator(|propagator| {
        Json(inject_propagator_context(propagator, &Context::current()))
    })
}

fn inject_propagator_context(
    propagator: &dyn TextMapPropagator,
    context: &Context,
) -> HashMap<String, String> {
    let mut headers = HeaderMap::new();
    propagator.inject_context(context, &mut HeaderInjector(&mut headers));
    header_map_to_string_map(&headers)
}

fn header_map_to_string_map(headers: &HeaderMap) -> HashMap<String, String> {
    headers
        .iter()
        .filter_map(|(name, value)| {
            value
                .to_str()
                .ok()
                .map(|value| (name.as_str().to_owned(), value.to_owned()))
        })
        .collect()
}

async fn returnheaders(headers: HeaderMap) -> Json<HashMap<String, String>> {
    Json(header_map_to_string_map(&headers))
}

async fn requestdownstream(State(state): State<AppState>, method: Method) -> Response {
    let client = ClientBuilder::new(reqwest::Client::new())
        .with(TracingMiddleware::<DatadogClientSpanBackend>::new())
        .build();

    match client.request(method, &state.downstream_url).send().await {
        Ok(response) if response.status().is_success() => match response.bytes().await {
            Ok(body) => match serde_json::from_slice::<serde_json::Value>(&body) {
                Ok(body) => Json(body).into_response(),
                Err(error) => {
                    tracing::warn!("requestdownstream received a non-JSON response: {error}");
                    StatusCode::INTERNAL_SERVER_ERROR.into_response()
                }
            },
            Err(error) => {
                tracing::warn!("requestdownstream could not read the downstream response: {error}");
                StatusCode::INTERNAL_SERVER_ERROR.into_response()
            }
        },
        Ok(response) => {
            tracing::warn!(status = %response.status(), "requestdownstream received a downstream error");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
        Err(error) => {
            tracing::warn!("requestdownstream failed: {error}");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

// ─── External request endpoints ─────────────────────────────────────────────

async fn make_distant_call(Query(params): Query<HashMap<String, String>>) -> Response {
    let url = params.get("url").cloned().unwrap_or_default();

    let capture_request_headers = integration::CaptureRequestHeaders::new();
    let client = ClientBuilder::new(reqwest::Client::new())
        .with(TracingMiddleware::<DatadogClientSpanBackend>::new())
        .with(capture_request_headers.clone())
        .build();

    let resp = client.get(&url).send().await;

    match resp {
        Ok(r) => {
            let status = r.status().as_u16();
            let request_headers = capture_request_headers.take_headers();
            let response_headers = integration::header_map_to_string_map(r.headers());
            Json(serde_json::json!({
                "url": url,
                "status_code": status,
                "request_headers": request_headers,
                "response_headers": response_headers
            }))
            .into_response()
        }
        Err(e) => {
            tracing::warn!("make_distant_call failed: {e}");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}
