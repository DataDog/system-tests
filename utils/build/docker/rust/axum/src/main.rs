use std::collections::HashMap;
use std::str::FromStr as _;
use std::sync::OnceLock;

use axum::{
    body::Bytes,
    extract::{MatchedPath, Path, Query, Request},
    http::{HeaderMap, HeaderName, HeaderValue, Method, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    routing::{get, options, post},
    Extension, Json, Router,
};
use opentelemetry::{
    global::{self, BoxedTracer},
    trace::{Span as _, SpanKind, Status, TraceContextExt as _, Tracer as _},
    Context, KeyValue,
};
use opentelemetry_http::HeaderExtractor;
use serde::Deserialize;
use serde_json::{json, Value};
use tracing::{level_filters::LevelFilter, Level};
use tracing_subscriber::{layer::SubscriberExt as _, util::SubscriberInitExt as _};

const VERSION_FILE: &str = "/app/SYSTEM_TESTS_LIBRARY_VERSION";

/// Single runtime-id for the lifetime of this process.
static RUNTIME_ID: OnceLock<String> = OnceLock::new();
fn runtime_id() -> &'static str {
    RUNTIME_ID.get_or_init(|| uuid::Uuid::new_v4().to_string())
}

/// Process-wide handle to the datadog-opentelemetry tracer.
///
/// `datadog_opentelemetry::tracing().init()` registers itself as the global
/// tracer provider, so `global::tracer(..)` returns the Datadog tracer. Creating
/// spans through this (instead of via the `tracing` crate + a bridge layer) is
/// what keeps the `opentelemetry` dependency free to float across dd-trace-rs
/// versions.
fn tracer() -> &'static BoxedTracer {
    static TRACER: OnceLock<BoxedTracer> = OnceLock::new();
    TRACER.get_or_init(|| global::tracer("weblog"))
}

/// The per-request server span, threaded to handlers via request extensions so
/// they can enrich it without relying on a thread-local "current span".
#[derive(Clone)]
struct ServerSpan(Context);

#[tokio::main]
async fn main() {
    let tracer_provider = datadog_opentelemetry::tracing().init();
    let meter_provider = datadog_opentelemetry::metrics().init();

    let fmt = tracing_subscriber::fmt::layer().json().with_level(true);

    tracing_subscriber::registry()
        .with(LevelFilter::from_level(Level::TRACE))
        .with(fmt)
        .init();

    opentelemetry::global::set_meter_provider(meter_provider.clone());

    let app = Router::new()
        // Root endpoint
        .route("/", get(index))
        .route("/", post(index))
        .route("/", options(index))
        // Basic info endpoints
        .route("/healthcheck", get(healthcheck))
        .route("/headers", get(headers_endpoint))
        .route("/status", get(status_endpoint))
        .route("/stats-unique", get(stats_unique))
        .route("/read_file", get(read_file))
        .route("/log/library", get(log_library))
        // Identification endpoints
        .route("/identify", get(identify))
        .route("/identify-propagate", get(identify_propagate))
        // Path parameter endpoints
        .route("/params/{value}", get(params_endpoint))
        .route("/sample_rate_route/{i}", get(sample_rate_route))
        // Span endpoints
        .route("/spans", get(spans_endpoint))
        // Tag value endpoint
        .route("/tag_value/{tag_value}/{status_code}", get(tag_value))
        .route("/tag_value/{tag_value}/{status_code}", post(tag_value))
        .route("/tag_value/{tag_value}/{status_code}", options(tag_value))
        // RASP / SQL endpoints (used by client-side stats obfuscation tests)
        .route("/rasp/sqli", get(rasp_sqli))
        .route("/rasp/sqli", post(rasp_sqli))
        // External request endpoints
        .route("/make_distant_call", get(make_distant_call))
        // Service overrides
        .route("/createextraservice", get(create_extra_service))
        // e2e span endpoints
        .route("/e2e_single_span", get(e2e_single_span))
        .route("/e2e_otel_span", get(e2e_otel_span))
        // endpoint_fallback
        .route("/endpoint_fallback", get(endpoint_fallback))
        .route_layer(axum::middleware::from_fn(server_span))
        .into_make_service();

    let listener = tokio::net::TcpListener::bind("0.0.0.0:7777").await.unwrap();
    println!("Listening on port 7777");
    axum::serve(listener, app).await.unwrap();

    meter_provider.shutdown().unwrap();
    tracer_provider.shutdown().unwrap();
}

/// Datadog semantic-convention tags every span needs to satisfy
/// `validate_all_spans` in system-tests.
fn dd_tags() -> Vec<KeyValue> {
    vec![
        KeyValue::new("language", "rust"),
        KeyValue::new("component", "axum"),
        KeyValue::new("runtime-id", runtime_id()),
        // process_id goes to the metrics map (numeric value).
        KeyValue::new("process_id", std::process::id() as i64),
    ]
}

/// Middleware that opens the root HTTP server span for the request.
///
/// This replaces tower-otel's HTTP layer: it extracts any upstream trace context,
/// starts a server-kind OTel span with the HTTP semantic + Datadog tags, exposes
/// it to handlers through the request extensions, and closes it once the response
/// is ready.
async fn server_span(matched_path: MatchedPath, mut req: Request, next: Next) -> Response {
    // Continue an upstream distributed trace if the propagation headers are present.
    let parent_cx =
        global::get_text_map_propagator(|prop| prop.extract(&HeaderExtractor(req.headers())));

    let route = matched_path.as_str().to_owned();
    let method = req.method().to_string();

    let host = req
        .headers()
        .get(axum::http::header::HOST)
        .and_then(|h| h.to_str().ok())
        .unwrap_or("localhost:7777")
        .to_owned();
    let server_address = host.split(':').next().unwrap_or(&host).to_owned();
    let path = req.uri().path().to_owned();
    // http.url from the request URI + host header (with sensitive params scrubbed)
    let query_scrubbed = req
        .uri()
        .query()
        .map(scrub_query_string)
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let url = format!("http://{host}{path}{query_scrubbed}");

    let mut attributes = dd_tags();
    // _dd.top_level marks this as a root span so the library interface can
    // match traces to requests via the user-agent header.
    attributes.push(KeyValue::new("_dd.top_level", 1i64));
    attributes.push(KeyValue::new("http.request.method", method.clone()));
    attributes.push(KeyValue::new("http.route", route.clone()));
    attributes.push(KeyValue::new("url.path", path));
    attributes.push(KeyValue::new("url.scheme", "http"));
    attributes.push(KeyValue::new("network.protocol.name", "http"));
    attributes.push(KeyValue::new("server.address", server_address));
    attributes.push(KeyValue::new("http.url", url));

    // http.referrer_hostname from the Referer header
    if let Some(referer) = req.headers().get(axum::http::header::REFERER) {
        if let Ok(referer_str) = referer.to_str() {
            if let Some(hostname) = extract_hostname_from_referer(referer_str) {
                attributes.push(KeyValue::new("http.referrer_hostname", hostname));
            }
        }
    }
    // http.useragent from the User-Agent header
    if let Some(ua) = req.headers().get(axum::http::header::USER_AGENT) {
        if let Ok(ua_str) = ua.to_str() {
            attributes.push(KeyValue::new("http.useragent", ua_str.to_owned()));
        }
    }
    // http.client_ip / network.client.ip from the best IP header available
    if let Some(ip) = extract_client_ip(req.headers()) {
        attributes.push(KeyValue::new("http.client_ip", ip.clone()));
        attributes.push(KeyValue::new("network.client.ip", ip));
    }

    let span = tracer()
        .span_builder(format!("{method} {route}"))
        .with_kind(SpanKind::Server)
        .with_attributes(attributes)
        .start_with_context(tracer(), &parent_cx);

    let cx = parent_cx.with_span(span);
    req.extensions_mut().insert(ServerSpan(cx.clone()));

    let response = next.run(req).await;

    let status = response.status();
    {
        let span = cx.span();
        span.set_attribute(KeyValue::new(
            "http.response.status_code",
            status.as_u16() as i64,
        ));
        // Mark 5xx server errors on the span
        if status.is_server_error() {
            span.set_status(Status::Error {
                description: format!("HTTP {}", status.as_u16()).into(),
            });
        }
    }
    cx.span().end();
    response
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

fn scrub_query_string(query: &str) -> String {
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

// ─── Basic endpoints ───────────────────────────────────────────────────────────

async fn healthcheck() -> Json<Value> {
    let version = std::fs::read_to_string(VERSION_FILE).unwrap_or_else(|_| "unknown".to_string());
    let version = version.trim().to_string();
    Json(json!({
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

async fn headers_endpoint() -> Response {
    (
        StatusCode::OK,
        [("content-type", "text"), ("content-language", "en-US")],
        "Hello headers!\n",
    )
        .into_response()
}

async fn status_endpoint(Query(params): Query<HashMap<String, String>>) -> Response {
    let code = params
        .get("code")
        .and_then(|c| c.parse::<u16>().ok())
        .unwrap_or(200);
    let status = StatusCode::from_u16(code).unwrap_or(StatusCode::OK);
    (status, format!("status: {code}")).into_response()
}

async fn stats_unique(Query(params): Query<HashMap<String, String>>) -> Response {
    let code = params
        .get("code")
        .and_then(|code| StatusCode::from_str(code).ok())
        .unwrap_or(StatusCode::OK);
    if code == StatusCode::NO_CONTENT {
        StatusCode::NO_CONTENT.into_response()
    } else {
        (code, "OK, probably").into_response()
    }
}

async fn read_file(Query(params): Query<HashMap<String, String>>) -> Response {
    let file = params.get("file").cloned().unwrap_or_default();
    match std::fs::read_to_string(&file) {
        Ok(content) => (StatusCode::OK, content).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Error: {e}")).into_response(),
    }
}

async fn log_library(Query(params): Query<HashMap<String, String>>) -> Response {
    let msg = params
        .get("msg")
        .cloned()
        .unwrap_or_else(|| "msg".to_string());
    let level = params
        .get("level")
        .cloned()
        .unwrap_or_else(|| "info".to_string());
    let log_msg = format!("{{\"message\": \"{msg}\", \"level\": \"{level}\"}}");
    match level.as_str() {
        "error" => tracing::error!("{}", log_msg),
        "warn" | "warning" => tracing::warn!("{}", log_msg),
        "debug" => tracing::debug!("{}", log_msg),
        _ => tracing::info!("{}", log_msg),
    }
    (StatusCode::OK, "").into_response()
}

// ─── Identification endpoints ──────────────────────────────────────────────────

async fn identify(Extension(ServerSpan(cx)): Extension<ServerSpan>) -> Response {
    let span = cx.span();
    span.set_attribute(KeyValue::new("usr.id", "usr.id"));
    span.set_attribute(KeyValue::new("usr.email", "usr.email"));
    span.set_attribute(KeyValue::new("usr.name", "usr.name"));
    span.set_attribute(KeyValue::new("usr.session_id", "usr.session_id"));
    span.set_attribute(KeyValue::new("usr.role", "usr.role"));
    span.set_attribute(KeyValue::new("usr.scope", "usr.scope"));
    (StatusCode::OK, "").into_response()
}

async fn identify_propagate(Extension(ServerSpan(cx)): Extension<ServerSpan>) -> Response {
    let span = cx.span();
    span.set_attribute(KeyValue::new("usr.id", "usr.id"));
    // base64 encoding of "usr.id"
    span.set_attribute(KeyValue::new("_dd.p.usr.id", "dXNyLmlk"));
    (StatusCode::OK, "").into_response()
}

// ─── Path parameter endpoints ─────────────────────────────────────────────────

async fn params_endpoint(Path(_value): Path<String>) -> &'static str {
    "Hello world!\n"
}

async fn sample_rate_route(Path(_i): Path<String>) -> &'static str {
    "Hello world!\n"
}

// ─── Spans endpoint ───────────────────────────────────────────────────────────

async fn spans_endpoint(Query(params): Query<HashMap<String, String>>) -> Response {
    let repeats: u32 = params
        .get("repeats")
        .and_then(|v| v.parse().ok())
        .unwrap_or(1);
    let garbage: u32 = params
        .get("garbage")
        .and_then(|v| v.parse().ok())
        .unwrap_or(1);

    for _ in 0..repeats {
        let mut attributes = dd_tags();
        for i in 0..garbage {
            attributes.push(KeyValue::new(format!("garbage{i}"), format!("Random string {i}")));
        }
        // A detached root span (equivalent to the old `parent: None`).
        let mut span = tracer()
            .span_builder("custom.span")
            .with_attributes(attributes)
            .start_with_context(tracer(), &Context::new());
        span.end();
    }

    let body = format!("Generated {repeats} spans with {garbage} garbage tags\n");
    (StatusCode::OK, body).into_response()
}

// ─── Tag value endpoint ────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct TagValuePath {
    tag_value: String,
    status_code: u16,
}

async fn tag_value(
    Extension(ServerSpan(cx)): Extension<ServerSpan>,
    Path(path): Path<TagValuePath>,
    Query(query_params): Query<HashMap<String, String>>,
    method: Method,
    _headers: HeaderMap,
    body: Bytes,
) -> Response {
    cx.span().set_attribute(KeyValue::new(
        "appsec.events.system_tests_appsec_event.value",
        path.tag_value.clone(),
    ));

    let status = StatusCode::from_u16(path.status_code).unwrap_or(StatusCode::OK);

    // Check if the tag_value starts with "payload_in_response_body" and method is POST
    if method == Method::POST && path.tag_value.starts_with("payload_in_response_body") {
        // Try to parse the body as JSON
        let payload: Value = serde_json::from_slice(&body).unwrap_or(Value::Null);
        let mut response_headers = HeaderMap::new();
        for (k, v) in &query_params {
            if let (Ok(name), Ok(val)) = (HeaderName::from_str(k), HeaderValue::from_str(v)) {
                response_headers.insert(name, val);
            }
        }
        response_headers.insert(
            axum::http::header::CONTENT_TYPE,
            HeaderValue::from_static("application/json"),
        );
        let resp_body = json!({ "payload": payload });
        return (status, response_headers, Json(resp_body)).into_response();
    }

    // Set query params as response headers
    let mut response_headers = HeaderMap::new();
    for (k, v) in &query_params {
        if let (Ok(name), Ok(val)) = (HeaderName::from_str(k), HeaderValue::from_str(v)) {
            response_headers.insert(name, val);
        }
    }

    (status, response_headers, "Value tagged").into_response()
}

// ─── RASP / SQL endpoints ──────────────────────────────────────────────────────

/// Emit a SQL client span with a raw (unobfuscated) statement so that the tracer
/// exercises its client-side stats obfuscation. Distinct `user_id` values produce
/// distinct raw resources that all normalise to `SELECT * FROM users WHERE id = ?`
/// once obfuscated.
async fn rasp_sqli(Query(params): Query<HashMap<String, String>>) -> Response {
    let user_id = params.get("user_id").cloned().unwrap_or_default();
    let statement = format!("SELECT * FROM users WHERE id = '{user_id}'");

    let mut attributes = dd_tags();
    attributes.push(KeyValue::new("db.system", "sqlite"));
    attributes.push(KeyValue::new("db.statement", statement));

    let mut span = tracer()
        .span_builder("sqlite.query")
        .with_kind(SpanKind::Client)
        .with_attributes(attributes)
        .start_with_context(tracer(), &Context::new());
    span.end();

    StatusCode::OK.into_response()
}

// ─── External request endpoints ───────────────────────────────────────────────

async fn make_distant_call(
    Extension(ServerSpan(server_cx)): Extension<ServerSpan>,
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let url = params.get("url").cloned().unwrap_or_default();
    let parsed = reqwest::Url::parse(&url).ok();
    let host = parsed
        .as_ref()
        .and_then(|u| u.host_str().map(str::to_owned))
        .unwrap_or_default();

    // Build scrubbed URL for the client span's http.url tag (preserving port)
    let scrubbed_url = parsed
        .as_ref()
        .map(|u| {
            let path = u.path();
            let query_scrubbed = u.query().map(scrub_query_string);
            let qs = query_scrubbed
                .as_deref()
                .map(|q| format!("?{q}"))
                .unwrap_or_default();
            let host_port = match u.port() {
                Some(p) => format!("{}:{}", u.host_str().unwrap_or(""), p),
                None => u.host_str().unwrap_or("").to_string(),
            };
            format!("{}://{}{}{}", u.scheme(), host_port, path, qs)
        })
        .unwrap_or_else(|| url.clone());

    let mut attributes = dd_tags();
    attributes.push(KeyValue::new("http.request.method", "GET"));
    attributes.push(KeyValue::new("server.address", host.clone()));
    attributes.push(KeyValue::new("out.host", host));
    attributes.push(KeyValue::new("network.protocol.name", "http"));
    attributes.push(KeyValue::new("http.url", scrubbed_url));
    attributes.push(KeyValue::new("span.kind", "client"));

    // Child of the current server span.
    let mut span = tracer()
        .span_builder("http.client.request")
        .with_kind(SpanKind::Client)
        .with_attributes(attributes)
        .start_with_context(tracer(), &server_cx);

    let resp = reqwest::Client::new().get(&url).send().await;

    match resp {
        Ok(r) => {
            let status = r.status().as_u16();
            // Set as both string (meta) and int (metrics) for compatibility
            span.set_attribute(KeyValue::new("http.status_code", status.to_string()));
            span.set_attribute(KeyValue::new("http.response.status_code", status as i64));
            if status >= 400 {
                span.set_attribute(KeyValue::new("error.type", "HTTP Error"));
                // Set OTel span status to Error — translated to error:1 by datadog-opentelemetry
                span.set_status(Status::Error {
                    description: format!("HTTP {status}").into(),
                });
            }
            span.end();
            Json(json!({
                "url": url,
                "status_code": status,
                "request_headers": {},
                "response_headers": {}
            }))
            .into_response()
        }
        Err(e) => {
            tracing::warn!("make_distant_call failed: {e}");
            span.end();
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

// ─── Service override ─────────────────────────────────────────────────────────

async fn create_extra_service(
    Extension(ServerSpan(cx)): Extension<ServerSpan>,
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let service_name = params.get("serviceName").cloned().unwrap_or_default();
    let span = cx.span();
    span.set_attribute(KeyValue::new("service.name", service_name.clone()));
    span.set_attribute(KeyValue::new("service", service_name));
    (StatusCode::OK, "").into_response()
}

// ─── e2e span endpoints ───────────────────────────────────────────────────────

async fn e2e_single_span(Query(params): Query<HashMap<String, String>>) -> Response {
    let parent_name = params.get("parentName").cloned().unwrap_or_default();
    let child_name = params.get("childName").cloned().unwrap_or_default();
    let should_index = params.get("shouldIndex").cloned().unwrap_or_default();

    let mut parent_attrs = vec![KeyValue::new("span.name", parent_name.clone())];
    if should_index == "1" {
        parent_attrs.push(KeyValue::new("_dd.filter.kept", 1i64));
        parent_attrs.push(KeyValue::new("manual.keep", "true"));
    }
    // Detached root span (equivalent to the old `parent: None`).
    let parent_span = tracer()
        .span_builder("e2e.single.span")
        .with_attributes(parent_attrs)
        .start_with_context(tracer(), &Context::new());
    let parent_cx = Context::new().with_span(parent_span);

    let mut child_attrs = vec![KeyValue::new("span.name", child_name.clone())];
    if should_index == "1" {
        child_attrs.push(KeyValue::new("_dd.filter.kept", 1i64));
        child_attrs.push(KeyValue::new("manual.keep", "true"));
    }
    let mut child_span = tracer()
        .span_builder("e2e.child.span")
        .with_attributes(child_attrs)
        .start_with_context(tracer(), &parent_cx);
    child_span.end();

    parent_cx.span().end();

    (StatusCode::OK, "").into_response()
}

async fn e2e_otel_span(Query(params): Query<HashMap<String, String>>) -> Response {
    let parent_name = params.get("parentName").cloned().unwrap_or_default();
    let child_name = params.get("childName").cloned().unwrap_or_default();
    let should_index = params.get("shouldIndex").cloned().unwrap_or_default();

    let tracer = tracer();

    let mut parent_builder = tracer.span_builder(parent_name.clone());
    parent_builder.span_kind = Some(SpanKind::Internal);
    let mut parent_span = tracer.build(parent_builder);

    parent_span.set_attribute(KeyValue::new("operation.name", parent_name.clone()));
    if should_index == "1" {
        parent_span.set_attribute(KeyValue::new("_dd.filter.kept", 1i64));
        parent_span.set_attribute(KeyValue::new("sampling.priority", 2i64));
    }

    let cx = Context::current_with_span(parent_span);
    {
        let mut child_builder = tracer.span_builder(child_name.clone());
        child_builder.span_kind = Some(SpanKind::Internal);
        let mut child_span = tracer.build_with_context(child_builder, &cx);
        child_span.set_attribute(KeyValue::new("operation.name", child_name.clone()));
        if should_index == "1" {
            child_span.set_attribute(KeyValue::new("_dd.filter.kept", 1i64));
            child_span.set_attribute(KeyValue::new("sampling.priority", 2i64));
        }
        child_span.end();
    }

    cx.span().end();

    (StatusCode::OK, "").into_response()
}

// ─── endpoint_fallback ────────────────────────────────────────────────────────

async fn endpoint_fallback(
    Extension(ServerSpan(cx)): Extension<ServerSpan>,
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let case = params.get("case").cloned().unwrap_or_default();
    let span = cx.span();

    match case.as_str() {
        "with_route" => {
            span.set_attribute(KeyValue::new("http.route", "/users/{id}/profile"));
            (StatusCode::OK, "").into_response()
        }
        "with_endpoint" => {
            span.set_attribute(KeyValue::new("http.endpoint", "/api/products/{param:int}"));
            (StatusCode::OK, "").into_response()
        }
        "404" => {
            span.set_attribute(KeyValue::new("http.endpoint", "/api/notfound/{param:int}"));
            (StatusCode::NOT_FOUND, "").into_response()
        }
        "computed" => {
            span.set_attribute(KeyValue::new(
                "http.url",
                "http://localhost:8080/endpoint_fallback_computed/users/123/orders/456",
            ));
            (StatusCode::OK, "").into_response()
        }
        _ => (StatusCode::OK, "").into_response(),
    }
}
