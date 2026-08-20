//! Reqwest client-side span enrichment and header capture.

use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};

use http::Extensions;
use opentelemetry::trace::Status;
use reqwest_middleware::Middleware;
use reqwest_tracing::{reqwest_otel_span, ReqwestOtelSpanBackend};
use tracing::Span;
use tracing_opentelemetry::OpenTelemetrySpanExt;

use super::dd_tags;

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
        let host_port = req
            .url()
            .port()
            .map_or_else(|| host.clone(), |p| format!("{host}:{p}"));
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
