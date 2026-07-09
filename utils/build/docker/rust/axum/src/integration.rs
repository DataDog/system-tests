use std::{
    collections::HashMap,
    sync::{Arc, Mutex, OnceLock},
};

use axum::{extract::Request, http::HeaderMap, middleware::Next, response::Response};

use http::Extensions;
use opentelemetry::{trace::Status, KeyValue};
use reqwest_middleware::Middleware;
use reqwest_tracing::reqwest_otel_span;
use tracing::Span;
use tracing_opentelemetry::OpenTelemetrySpanExt;

/// Adds Datadog-specific attributes on top of the generic OTel HTTP server
/// span that `axum_tracing_opentelemetry::middleware::OtelAxumLayer` already
/// created and made current for this request.
pub async fn enrich_span(request: Request, next: Next) -> Response {
    let span = Span::current();

    let host = request
        .headers()
        .get(axum::http::header::HOST)
        .and_then(|h| h.to_str().ok())
        .unwrap_or("localhost:7777")
        .to_owned();
    let server_address = host.split(':').next().unwrap_or(&host).to_owned();
    let path = request.uri().path().to_owned();
    // http.url from the request URI + host header (with sensitive params scrubbed)
    let query_scrubbed = request.uri().query().map(scrub_query_string);
    let query_suffix = query_scrubbed
        .as_deref()
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let url = format!("http://{host}{path}{query_suffix}");
    let method = request.method().to_string();

    for attr in build_attributes(method, &url, server_address) {
        span.set_attribute(attr.key, attr.value);
    }
    // _dd.top_level marks this as a root span so the library interface can
    // match traces to requests via the user-agent header.
    span.set_attribute("_dd.top_level", 1i64);
    span.set_attribute("url.path", path);
    // Overrides the raw (unscrubbed) url.query the OTel HTTP-server span
    // records by default.
    span.record("url.query", query_scrubbed.unwrap_or_default().as_str());

    // http.referrer_hostname from the Referer header
    if let Some(referer) = request.headers().get(axum::http::header::REFERER) {
        if let Ok(referer_str) = referer.to_str() {
            if let Some(hostname) = extract_hostname_from_referer(referer_str) {
                span.set_attribute("http.referrer_hostname", hostname);
            }
        }
    }
    // http.useragent from the User-Agent header
    if let Some(ua) = request.headers().get(axum::http::header::USER_AGENT) {
        if let Ok(ua_str) = ua.to_str() {
            span.set_attribute("http.useragent", ua_str.to_owned());
        }
    }
    // http.client_ip / network.client.ip from the best IP header available
    if let Some(ip) = extract_client_ip(request.headers()) {
        span.set_attribute("http.client_ip", ip.clone());
        span.set_attribute("network.client.ip", ip);
    }

    let response = next.run(request).await;

    let status = response.status();
    span.set_attribute("http.response.status_code", status.as_u16() as i64);
    // Mark 5xx server errors on the span
    if status.is_server_error() {
        span.set_status(Status::Error {
            description: format!("HTTP {}", status.as_u16()).into(),
        });
    }
    response
}

/// [`reqwest_tracing::ReqwestOtelSpanBackend`] that names outgoing spans
/// `http.client.request` and enriches them with the same Datadog
/// semantic-convention attributes used for inbound server spans.
pub struct DatadogClientSpanBackend;

impl reqwest_tracing::ReqwestOtelSpanBackend for DatadogClientSpanBackend {
    fn on_request_start(req: &reqwest::Request, _ext: &mut http::Extensions) -> Span {
        let span = reqwest_otel_span!(name = "http.client.request", req);

        let host = req.url().host_str().unwrap_or_default().to_owned();
        let query_scrubbed = req.url().query().map(scrub_query_string);
        let query_suffix = query_scrubbed.map(|q| format!("?{q}")).unwrap_or_default();
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

// ─── URL helpers ────────────────────────────────────────────────────────────────────

/// Sensitive query parameter key patterns (case-insensitive substrings).
const SENSITIVE_KEYS: &[&str] = &[
    "pass",
    "password",
    "secret",
    "api_key",
    "apikey",
    "auth",
    "credentials",
    "mysql_pwd",
    "private_key",
    "public_key",
    "token",
    "application_key",
    "access_token",
    "client_secret",
];

fn is_sensitive_key(key: &str) -> bool {
    let lower = key.to_lowercase();
    SENSITIVE_KEYS.iter().any(|&s| lower.contains(s))
}

pub fn scrub_query_string(query: &str) -> String {
    let mut parts = Vec::new();
    for pair in query.split('&') {
        if let Some(eq_pos) = pair.find('=') {
            let key = &pair[..eq_pos];
            if is_sensitive_key(key) {
                // Replace the entire key=value pair with <redacted>
                parts.push("<redacted>".to_owned());
            } else {
                parts.push(pair.to_owned());
            }
        } else {
            parts.push(pair.to_owned());
        }
    }
    parts.join("&")
}

fn extract_hostname_from_referer(referer: &str) -> Option<String> {
    if referer.is_empty() {
        return None;
    }
    // Only http/https schemes
    let rest = referer
        .strip_prefix("https://")
        .or_else(|| referer.strip_prefix("http://"))?;

    // Strip userinfo if present (user:pass@)
    let rest = if let Some(at_pos) = rest.find('@') {
        &rest[at_pos + 1..]
    } else {
        rest
    };

    // Hostname ends at '/', '?', '#', or ':' (port)
    let end = rest
        .find(|c| c == '/' || c == '?' || c == '#' || c == ':')
        .unwrap_or(rest.len());
    let hostname = &rest[..end];
    if hostname.is_empty() {
        None
    } else {
        Some(hostname.to_owned())
    }
}

// ─── Client IP extraction ────────────────────────────────────────────────────

/// Extract the best client IP from the request headers.
/// Follows Datadog's priority order for IP headers.
fn extract_client_ip(headers: &HeaderMap) -> Option<String> {
    // Headers in priority order (single-value headers first, then multi-value)
    let priority_headers = [
        "x-client-ip",
        "x-real-ip",
        "true-client-ip",
        "fastly-client-ip",
        "cf-connecting-ip",
        "cf-connecting-ipv6",
        "x-forwarded-for",
        "forwarded-for",
        "x-cluster-client-ip",
    ];

    for header_name in &priority_headers {
        if let Some(value) = headers.get(*header_name) {
            if let Ok(value_str) = value.to_str() {
                // For comma-separated lists, find the first public IP
                for candidate in value_str.split(',') {
                    let ip = candidate.trim().to_owned();
                    if !ip.is_empty() && is_public_ip(&ip) {
                        return Some(ip);
                    }
                }
                // If no public IP found, return first non-empty
                if let Some(first) = value_str.split(',').next() {
                    let ip = first.trim().to_owned();
                    if !ip.is_empty() {
                        return Some(ip);
                    }
                }
            }
        }
    }
    None
}

/// Returns true if the IP is a publicly routable IP address.
fn is_public_ip(ip: &str) -> bool {
    use std::net::IpAddr;
    let Ok(addr) = ip.parse::<IpAddr>() else {
        return false;
    };
    match addr {
        IpAddr::V4(v4) => {
            !v4.is_private()
                && !v4.is_loopback()
                && !v4.is_link_local()
                && !v4.is_broadcast()
                && !v4.is_multicast()
                && !v4.is_unspecified()
        }
        IpAddr::V6(v6) => {
            !v6.is_loopback()
                && !v6.is_multicast()
                && !v6.is_unspecified()
                // filter link-local (fe80::/10)
                && (v6.segments()[0] & 0xffc0) != 0xfe80
                // filter unique-local (fc00::/7)
                && (v6.segments()[0] & 0xfe00) != 0xfc00
        }
    }
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
