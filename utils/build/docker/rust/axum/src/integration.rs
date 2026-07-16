//! Tracing and span-enrichment utilities for Datadog compatibility.
//!
//! This module adds Datadog-specific semantic-convention attributes to both
//! inbound (server) and outgoing (client) HTTP spans so they satisfy the
//! system-tests' `validate_all_spans` checks.
//!
//! Future work: If a proper datadog integration for axum gets implemented,
//! refactor to use it instead

use std::{
    collections::HashMap,
    sync::{Arc, Mutex, OnceLock},
};

use axum::{
    extract::Request,
    middleware::{self, Next},
    response::Response,
    Router,
};

use http::Extensions;
use opentelemetry::{
    trace::{Status, TraceContextExt, TracerProvider},
    Context, KeyValue,
};
use opentelemetry_sdk::trace::SdkTracerProvider;
use reqwest_middleware::Middleware;
use reqwest_tracing::{reqwest_otel_span, ReqwestOtelSpanBackend};
use tracing::Span;
use tracing_opentelemetry::OpenTelemetrySpanExt;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

/// Initializes the Datadog tracer provider and installs it as the global
/// `tracing` subscriber, so `tracing::info_span!` etc. produce Datadog-backed spans.
pub fn install_datadog_tracing() -> SdkTracerProvider {
    let tracer_provider = datadog_opentelemetry::tracing().init();
    tracing_subscriber::registry()
        .with(tracing_opentelemetry::layer().with_tracer(tracer_provider.tracer("weblog")))
        .init();
    tracer_provider
}

/// Helper returning datadog semantic-convention tags every span needs to satisfy
/// Used in both reqwest and axum middleware
/// (necesary for test `validate_all_spans`)
fn dd_tags() -> Vec<KeyValue> {
    /// Single runtime-id for the lifetime of this process.
    static RUNTIME_ID: OnceLock<String> = OnceLock::new();

    vec![
        KeyValue::new("language", "rust"),
        KeyValue::new("component", "axum"),
        KeyValue::new(
            "runtime-id",
            RUNTIME_ID
                .get_or_init(|| uuid::Uuid::new_v4().to_string())
                .as_str(),
        ),
        // process_id goes to the metrics map (numeric value).
        KeyValue::new("process_id", std::process::id() as i64),
    ]
}

/// Installs the Datadog-specific span-enrichment layer and the OTel HTTP
/// instrumentation layer onto the given router.
pub fn install_middleware(router: Router) -> Router {
    router
        .layer(middleware::from_fn(datadog_specific_axum_layer))
        .layer(opentelemetry_instrumentation_tower::HTTPLayer::default())
}

/// Adds Datadog-specific attributes on top of the OTel HTTP server span that
/// `opentelemetry_instrumentation_tower::HTTPLayer` created for this request.
///
/// `HTTPLayer` builds its span via `opentelemetry::Context`, not `tracing`,
/// so we use `Context::current().span()` instead of `tracing::Span::current()`.
/// Only attributes not already set by `HTTPLayer` are added here.
async fn datadog_specific_axum_layer(request: Request, next: Next) -> Response {
    let cx = Context::current();
    let span = cx.span();

    let host = request
        .headers()
        .get(axum::http::header::HOST)
        .and_then(|h| h.to_str().ok())
        .unwrap_or("localhost:7777")
        .to_owned();
    let server_address = host.split(':').next().unwrap_or(&host).to_owned();
    let path = request.uri().path().to_owned();
    // http.url from the request URI + host header. Query-string obfuscation is
    // a tracer responsibility, so the weblog reports the URL verbatim.
    let query_suffix = request
        .uri()
        .query()
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let url = format!("http://{host}{path}{query_suffix}");

    for attr in dd_tags() {
        span.set_attribute(attr);
    }
    span.set_attribute(KeyValue::new("http.url", url));
    span.set_attribute(KeyValue::new("server.address", server_address));
    // _dd.top_level marks this as a root span so the library interface can
    // match traces to requests via the user-agent header.
    span.set_attribute(KeyValue::new("_dd.top_level", 1i64));

    next.run(request).await
}

/// [`reqwest_tracing::ReqwestOtelSpanBackend`] that names outgoing spans
/// `http.client.request` and enriches them with the same Datadog
/// semantic-convention attributes used for inbound server spans.
pub struct DatadogClientSpanBackend;

impl ReqwestOtelSpanBackend for DatadogClientSpanBackend {
    fn on_request_start(req: &reqwest::Request, _ext: &mut http::Extensions) -> Span {
        let span = reqwest_otel_span!(name = "http.client.request", req);

        let host = req.url().host_str().unwrap_or_default().to_owned();
        let query_suffix = req
            .url()
            .query()
            .map(|q| format!("?{q}"))
            .unwrap_or_default();
        let host_port = match req.url().port() {
            Some(p) => format!("{host}:{p}"),
            None => host.clone(),
        };
        let scrubbed_url = format!(
            "{}://{}{}{}",
            req.url().scheme(),
            host_port,
            req.url().path(),
            query_suffix
        );

        for attr in dd_tags() {
            span.set_attribute(attr.key, attr.value);
        }
        span.set_attribute("http.request.method", req.method().to_string());
        span.set_attribute("http.url", scrubbed_url);
        span.set_attribute("server.address", host.clone());
        span.set_attribute("out.host", host);
        span.set_attribute("network.protocol.name", "http");
        span
    }

    fn on_request_end(
        span: &Span,
        outcome: &reqwest_middleware::Result<reqwest::Response>,
        _ext: &mut http::Extensions,
    ) {
        reqwest_tracing::default_on_request_end(span, outcome);
        if let Ok(response) = outcome {
            let status = response.status().as_u16();
            span.set_attribute("http.status_code", status.to_string());
            if status >= 400 {
                span.set_attribute("error.type", "HTTP Error");
                span.set_status(Status::Error {
                    description: format!("HTTP {status}").into(),
                });
            }
        }
    }
}

/// Records the outgoing request's headers. Construct it, hand a clone to `ClientBuilder::with`, then read the
/// headers back afterwards with `take_headers`. Useful for make_distant_call
#[derive(Clone, Default)]
pub struct CaptureRequestHeaders {
    headers: Arc<Mutex<Option<HashMap<String, String>>>>,
}

impl CaptureRequestHeaders {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns the headers captured for the most recent request, if any.
    pub fn take_headers(&self) -> HashMap<String, String> {
        self.headers.lock().unwrap().take().unwrap_or_default()
    }
}

#[async_trait::async_trait]
impl Middleware for CaptureRequestHeaders {
    async fn handle(
        &self,
        req: reqwest::Request,
        extensions: &mut Extensions,
        next: reqwest_middleware::Next<'_>,
    ) -> reqwest_middleware::Result<reqwest::Response> {
        *self.headers.lock().unwrap() = Some(header_map_to_string_map(req.headers()));
        next.run(req, extensions).await
    }
}

/// Converts a `reqwest::header::HeaderMap` into a `HashMap<String, String>`, dropping invalid UTF-8 values
pub fn header_map_to_string_map(headers: &reqwest::header::HeaderMap) -> HashMap<String, String> {
    headers
        .iter()
        .filter_map(|(name, value)| {
            value
                .to_str()
                .ok()
                .map(|v| (name.as_str().to_owned(), v.to_owned()))
        })
        .collect()
}
