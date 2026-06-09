// Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
// This product includes software developed at Datadog (https://www.datadoghq.com/).
// Copyright 2024 Datadog, Inc.

//! Minimal end-to-end weblog for the Datadog Rust tracer (dd-trace-rs).
//!
//! It exposes the endpoints the system-tests end-to-end scenarios hit:
//!   - `GET /`                  -> a single server span
//!   - `GET /make_distant_call` -> a server span + an outbound HTTP client span
//!   - `GET /healthcheck`       -> readiness probe consumed by the test harness
//!
//! OTLP export behavior is entirely env-driven by the scenario (OTEL_TRACES_EXPORTER,
//! OTEL_EXPORTER_OTLP_TRACES_ENDPOINT, ...), so the app only has to initialize the
//! tracer normally and produce the expected spans.

use std::collections::HashMap;
use std::env;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};

use axum::{
    extract::Query,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use opentelemetry::{
    global,
    trace::{Span, SpanKind, Status, TraceContextExt, Tracer},
    Context, KeyValue,
};
use opentelemetry_http::HeaderInjector;
use opentelemetry_sdk::trace::SdkTracerProvider;
use serde::Serialize;
use serde_json::json;
use tokio::net::TcpListener;
use tokio::signal::unix::{signal, SignalKind};

// Datadog-tracer attribute conventions. The tracer maps these OTel semantic-convention
// keys onto the Datadog span fields the OTLP tests assert against:
//   http.request.method        -> http.method
//   http.response.status_code  -> http.status_code
//   user_agent.original        -> http.useragent  (used by the harness to match the request)
const ATTR_HTTP_REQUEST_METHOD: &str = "http.request.method";
const ATTR_HTTP_RESPONSE_STATUS_CODE: &str = "http.response.status_code";
const ATTR_URL_PATH: &str = "url.path";
const ATTR_USER_AGENT_ORIGINAL: &str = "user_agent.original";

fn user_agent(headers: &HeaderMap) -> String {
    headers
        .get(axum::http::header::USER_AGENT)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_string()
}

/// Build the common HTTP server-span attributes. Setting `user_agent.original` is what lets the
/// system-tests harness correlate the exported span back to the originating request (it injects a
/// `rid/<id>` token into the User-Agent header and looks it up in `http.useragent`).
fn server_span_attributes(method: &str, path: &str, headers: &HeaderMap, status: i64) -> Vec<KeyValue> {
    vec![
        KeyValue::new(ATTR_HTTP_REQUEST_METHOD, method.to_string()),
        KeyValue::new(ATTR_URL_PATH, path.to_string()),
        KeyValue::new(ATTR_HTTP_RESPONSE_STATUS_CODE, status),
        KeyValue::new(ATTR_USER_AGENT_ORIGINAL, user_agent(headers)),
    ]
}

async fn healthcheck() -> impl IntoResponse {
    let version = env::var("SYSTEM_TESTS_LIBRARY_VERSION").unwrap_or_default();
    Json(json!({
        "status": "ok",
        "library": {
            "name": "rust",
            "version": version,
        }
    }))
}

async fn home(headers: HeaderMap) -> impl IntoResponse {
    let tracer = global::tracer("weblog");
    let mut span = tracer
        .span_builder("server.request")
        .with_kind(SpanKind::Server)
        .start(&tracer);
    span.set_status(Status::Unset);
    for kv in server_span_attributes("GET", "/", &headers, 200) {
        span.set_attribute(kv);
    }
    span.end();

    (StatusCode::OK, "Hello world!\n")
}

#[derive(Serialize)]
struct DistantCallResponse {
    url: String,
    status_code: u16,
    request_headers: HashMap<String, String>,
    response_headers: HashMap<String, String>,
}

async fn make_distant_call(headers: HeaderMap, Query(params): Query<HashMap<String, String>>) -> impl IntoResponse {
    let tracer = global::tracer("weblog");
    let mut server_span = tracer
        .span_builder("server.request")
        .with_kind(SpanKind::Server)
        .start(&tracer);
    server_span.set_status(Status::Unset);
    for kv in server_span_attributes("GET", "/make_distant_call", &headers, 200) {
        server_span.set_attribute(kv);
    }

    // Make the server span the active context so the outbound client span is a child of it,
    // producing the multi-span trace the 128-bit trace-id test needs.
    let cx = Context::current_with_span(server_span);

    let Some(url) = params.get("url").filter(|u| !u.is_empty()).cloned() else {
        // Match the contract of the other weblogs: no url => plain "OK".
        cx.span().end();
        return (StatusCode::OK, "OK").into_response();
    };

    let result = perform_distant_call(&cx, &url).await;

    cx.span().end();

    match result {
        Ok(body) => (StatusCode::OK, Json(body)).into_response(),
        Err(err) => {
            tracing::error!("make_distant_call failed: {err:#}");
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": err.to_string() })),
            )
                .into_response()
        }
    }
}

async fn perform_distant_call(parent_cx: &Context, url: &str) -> anyhow::Result<DistantCallResponse> {
    // Use the global (boxed) tracer so the produced span is Send + Sync and can be carried in a
    // Context across the await point below.
    let tracer = global::tracer("weblog");
    let mut client_span = tracer
        .span_builder("http.request")
        .with_kind(SpanKind::Client)
        .start_with_context(&tracer, parent_cx);
    client_span.set_attribute(KeyValue::new(ATTR_HTTP_REQUEST_METHOD, "GET"));

    let client_cx = parent_cx.with_span(client_span);

    // Inject the trace context into the outbound request headers so propagation is exercised.
    let mut injected_headers = reqwest::header::HeaderMap::new();
    global::get_text_map_propagator(|propagator| {
        propagator.inject_context(&client_cx, &mut HeaderInjector(&mut injected_headers));
    });

    let client = reqwest::Client::new();
    let response = client.get(url).headers(injected_headers.clone()).send().await?;
    let status = response.status();

    let request_headers = injected_headers
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_str().unwrap_or("").to_string()))
        .collect();
    let response_headers = response
        .headers()
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_str().unwrap_or("").to_string()))
        .collect();

    client_cx
        .span()
        .set_attribute(KeyValue::new(ATTR_HTTP_RESPONSE_STATUS_CODE, status.as_u16() as i64));
    client_cx.span().end();

    Ok(DistantCallResponse {
        url: url.to_string(),
        status_code: status.as_u16(),
        request_headers,
        response_headers,
    })
}

fn init_tracer() -> SdkTracerProvider {
    let _ = tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .try_init();

    // All Datadog/OTLP configuration is supplied through environment variables by the scenario.
    datadog_opentelemetry::tracing()
        .with_config(datadog_opentelemetry::configuration::Config::builder().build())
        .init()
}

#[tokio::main]
async fn main() {
    let provider = init_tracer();

    let app = Router::new()
        .route("/", get(home))
        .route("/make_distant_call", get(make_distant_call))
        .route("/healthcheck", get(healthcheck));

    let port: u16 = env::var("WEBLOG_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(7777);
    let addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::UNSPECIFIED), port);

    let listener = TcpListener::bind(addr).await.expect("bind weblog listener");
    tracing::info!("weblog listening on {addr}");

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("run weblog server");

    let _ = provider.shutdown();
}

async fn shutdown_signal() {
    let mut term = signal(SignalKind::terminate()).expect("install SIGTERM handler");
    term.recv().await;
}
