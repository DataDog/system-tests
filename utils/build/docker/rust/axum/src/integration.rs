use std::{
    collections::HashMap,
    sync::{Arc, Mutex, OnceLock},
};

use axum::{extract::Request, middleware::Next, response::Response};

use http::Extensions;
use opentelemetry::{
    trace::{Status, TraceContextExt},
    Context, KeyValue,
};
use reqwest_middleware::Middleware;
use reqwest_tracing::reqwest_otel_span;
use tracing::Span;
use tracing_opentelemetry::OpenTelemetrySpanExt;

/// Adds Datadog-specific attributes on top of the OTel HTTP server span that
/// `opentelemetry_instrumentation_tower::HTTPLayer` created for this request.
///
/// `HTTPLayer` builds its span directly via `opentelemetry::Context`, not the
/// `tracing` crate, so we read/write through `Context::current().span()`
/// rather than `tracing::Span::current()` (which would be a no-op span here).
/// Only attributes `HTTPLayer` doesn't already set are added, to avoid
/// duplicating its behavior (see `opentelemetry-instrumentation-tower`'s
/// `HTTPLayer::call`/`ResponseFuture::poll`, which set
/// `http.request.method`/`url.scheme`/`url.path`/`url.full`/
/// `user_agent.original`/`http.route` up front and `http.response.status_code`
/// plus a 5xx error status on completion).
pub async fn enrich_span(request: Request, next: Next) -> Response {
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

impl reqwest_tracing::ReqwestOtelSpanBackend for DatadogClientSpanBackend {
    fn on_request_start(req: &reqwest::Request, _ext: &mut http::Extensions) -> Span {
        let span = reqwest_otel_span!(name = "http.client.request", req);

        let host = req.url().host_str().unwrap_or_default().to_owned();
        let query_suffix = req.url().query().map(|q| format!("?{q}")).unwrap_or_default();
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

        for attr in build_attributes(req.method().to_string(), scrubbed_url, host.clone()) {
            span.set_attribute(attr.key, attr.value);
        }
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

/// Datadog semantic-convention tags every span needs to satisfy
/// `validate_all_spans` in system-tests.
pub fn dd_tags() -> Vec<KeyValue> {
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

pub fn build_attributes(
    request_method: impl ToString,
    url: impl ToString,
    server_address: impl ToString,
) -> Vec<KeyValue> {
    let mut attrs = dd_tags();
    attrs.push(KeyValue::new(
        "http.request.method",
        request_method.to_string(),
    ));
    attrs.push(KeyValue::new("http.url", url.to_string()));
    attrs.push(KeyValue::new("server.address", server_address.to_string()));
    attrs
}

// Middleware to capture headers

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

/// Records the headers of the outgoing request as they are right before
/// it's sent, i.e. after every earlier middleware (in particular
/// `TracingMiddleware`'s automatic OTel context injection) has run.
///
/// Construct it, hand a clone to `ClientBuilder::with` (`Middleware` impls
/// are shared via `Arc` internally, so all clones see the same captured
/// headers), then read them back afterwards with `take_headers`.
#[derive(Clone, Default)]
pub struct CaptureRequestHeaders(Arc<Mutex<Option<HashMap<String, String>>>>);

impl CaptureRequestHeaders {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns the headers captured for the most recent request, if any.
    pub fn take_headers(&self) -> HashMap<String, String> {
        self.0.lock().unwrap().take().unwrap_or_default()
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
        *self.0.lock().unwrap() = Some(header_map_to_string_map(req.headers()));
        next.run(req, extensions).await
    }
}
