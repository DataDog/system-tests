//! Reqwest client-side span enrichment and header capture.

use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};

use http::Extensions;
use opentelemetry::{
    global,
    trace::{FutureExt, SpanKind, Status, TraceContextExt, Tracer},
    Context, KeyValue,
};
use opentelemetry_http::HeaderInjector;
use reqwest_middleware::Middleware;

use super::dd_tags;

/// Reqwest middleware that creates the outgoing `http.client.request` span,
/// propagates its trace context in the request headers, and enriches it with
/// the same Datadog semantic-convention attributes used for inbound server spans.
#[derive(Clone, Copy, Default)]
pub struct DatadogClientSpanBackend;

impl DatadogClientSpanBackend {
    /// Starts the client span as a child of the current OpenTelemetry `Context`
    /// and returns a `Context` holding it.
    fn on_request_start(req: &reqwest::Request) -> Context {
        let url = req.url();
        let host = url.host_str().unwrap_or_default().to_owned();
        let query_suffix = url.query().map(|q| format!("?{q}")).unwrap_or_default();
        let host_port = url
            .port()
            .map_or_else(|| host.clone(), |p| format!("{host}:{p}"));
        let scrubbed_url = format!(
            "{}://{}{}{}",
            url.scheme(),
            host_port,
            url.path(),
            query_suffix
        );

        // OTel HTTP client-span attributes (semantic conventions) ...
        let mut attributes = vec![
            KeyValue::new("http.request.method", req.method().to_string()),
            KeyValue::new("url.scheme", url.scheme().to_owned()),
        ];
        if let Some(port) = url.port_or_known_default() {
            attributes.push(KeyValue::new("server.port", i64::from(port)));
        }
        if let Some(user_agent) = req
            .headers()
            .get(http::header::USER_AGENT)
            .and_then(|v| v.to_str().ok())
        {
            attributes.push(KeyValue::new("user_agent.original", user_agent.to_owned()));
        }
        // ... plus the Datadog-specific attributes.
        attributes.extend(dd_tags());
        attributes.push(KeyValue::new("http.url", scrubbed_url));
        attributes.push(KeyValue::new("server.address", host.clone()));
        attributes.push(KeyValue::new("out.host", host));
        attributes.push(KeyValue::new("network.protocol.name", "http"));

        let parent_cx = Context::current();
        let tracer = global::tracer("weblog");
        let span = tracer
            .span_builder("http.client.request")
            .with_kind(SpanKind::Client)
            .with_attributes(attributes)
            .start_with_context(&tracer, &parent_cx);
        parent_cx.with_span(span)
    }

    /// Records the request outcome on the client span and ends it.
    fn on_request_end(cx: &Context, outcome: &reqwest_middleware::Result<reqwest::Response>) {
        let span = cx.span();
        match outcome {
            Ok(response) => {
                let status = response.status().as_u16();
                span.set_attribute(KeyValue::new(
                    "http.response.status_code",
                    i64::from(status),
                ));
                span.set_attribute(KeyValue::new("http.status_code", status.to_string()));
                if status >= 400 {
                    span.set_attribute(KeyValue::new("error.type", "HTTP Error"));
                    span.set_status(Status::Error {
                        description: format!("HTTP {status}").into(),
                    });
                }
            }
            Err(error) => {
                if let Some(status) = error.status() {
                    span.set_attribute(KeyValue::new(
                        "http.response.status_code",
                        i64::from(status.as_u16()),
                    ));
                }
                span.set_attribute(KeyValue::new("error.message", error.to_string()));
                span.set_status(Status::Error {
                    description: error.to_string().into(),
                });
            }
        }
        span.end();
    }
}

#[async_trait::async_trait]
impl Middleware for DatadogClientSpanBackend {
    async fn handle(
        &self,
        mut req: reqwest::Request,
        extensions: &mut Extensions,
        next: reqwest_middleware::Next<'_>,
    ) -> reqwest_middleware::Result<reqwest::Response> {
        let cx = Self::on_request_start(&req);

        // Propagate the client span's context so downstream spans join the same trace.
        global::get_text_map_propagator(|propagator| {
            propagator.inject_context(&cx, &mut HeaderInjector(req.headers_mut()));
        });

        let outcome = next.run(req, extensions).with_context(cx.clone()).await;
        Self::on_request_end(&cx, &outcome);
        outcome
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
