use std::collections::HashMap;
use std::str::FromStr as _;

use axum::{
    body::Bytes,
    extract::{MatchedPath, Path, Query, Request},
    http::{HeaderMap, HeaderName, HeaderValue, Method, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    routing::{any, get, options, post},
    Json, Router,
};
use opentelemetry::trace::TracerProvider as _;
use serde::Deserialize;
use serde_json::{json, Value};
use tower_otel::{metrics, trace};
use tracing::{level_filters::LevelFilter, Instrument as _, Level};
use tracing_opentelemetry::OpenTelemetrySpanExt as _;
use tracing_subscriber::{
    fmt::format::FmtSpan, layer::SubscriberExt as _, util::SubscriberInitExt, Layer as _,
};

const VERSION_FILE: &str = "/app/SYSTEM_TESTS_LIBRARY_VERSION";

#[tokio::main]
async fn main() {
    let tracer_provider = datadog_opentelemetry::tracing().init();
    let meter_provider = datadog_opentelemetry::metrics().init();

    const PKG_NAME: &str = env!("CARGO_PKG_NAME");

    let telemetry = tracing_opentelemetry::layer()
        .with_tracer(tracer_provider.tracer("default_tracer"))
        .with_tracked_inactivity(true)
        .with_filter(LevelFilter::TRACE);

    let fmt = tracing_subscriber::fmt::layer()
        .with_level(true)
        .with_span_events(FmtSpan::NEW | FmtSpan::CLOSE);

    tracing_subscriber::registry()
        .with(LevelFilter::from_level(Level::TRACE))
        .with(telemetry)
        .with(fmt)
        .init();

    opentelemetry::global::set_meter_provider(meter_provider.clone());
    let meter = opentelemetry::global::meter(PKG_NAME);

    let app = Router::new()
        // Root endpoint
        .route("/", get(index))
        .route("/", post(index))
        .route("/", options(index))
        // Basic info endpoints
        .route("/healthcheck", get(healthcheck))
        .route("/headers", get(headers_endpoint))
        .route("/html", get(html_endpoint))
        .route("/status", get(status_endpoint))
        .route("/stats-unique", get(stats_unique))
        .route("/flush", get(flush_endpoint))
        .route("/load_dependency", get(load_dependency))
        .route("/log/library", get(log_library))
        // Identification endpoints
        .route("/identify", get(identify))
        .route("/identify-propagate", get(identify_propagate))
        // Path parameter endpoints
        .route("/params/{value}", get(params_endpoint))
        .route("/sample_rate_route/{i}", get(sample_rate_route))
        .route("/api_security/sampling/{i}", get(api_security_sampling_i))
        .route("/api_security_sampling/{i}", get(api_security_sampling_standalone))
        // Span endpoints
        .route("/spans", get(spans_endpoint))
        // WAF endpoint — all methods, all sub-paths
        .route("/waf", any(waf_endpoint))
        .route("/waf/", any(waf_endpoint))
        .route("/waf/{*path}", any(waf_endpoint))
        // Tag value endpoint
        .route("/tag_value/{tag_value}/{status_code}", get(tag_value))
        .route("/tag_value/{tag_value}/{status_code}", post(tag_value))
        .route("/tag_value/{tag_value}/{status_code}", options(tag_value))
        // AppSec event tracking
        .route("/user_login_success_event", get(user_login_success_event))
        .route("/user_login_failure_event", get(user_login_failure_event))
        .route("/custom_event", get(custom_event))
        .route("/user_login_success_event_v2", post(user_login_success_event_v2))
        .route("/user_login_failure_event_v2", post(user_login_failure_event_v2))
        // AppSec blocking
        .route("/users", get(users_endpoint))
        // Downstream propagation
        .route("/returnheaders", get(return_headers))
        .route("/returnheaders", post(return_headers))
        .route("/requestdownstream", get(request_downstream))
        .route("/requestdownstream", post(request_downstream))
        .route("/vulnerablerequestdownstream", get(vulnerable_request_downstream))
        // Cookie endpoints
        .route("/set_cookie", get(set_cookie))
        .route("/session/new", get(session_new))
        // External request endpoints
        .route("/make_distant_call", get(make_distant_call))
        .route("/external_request", any(external_request))
        .route("/external_request/redirect", get(external_request_redirect))
        // Inferred proxy
        .route("/inferred-proxy/span-creation", get(inferred_proxy_span_creation))
        // Service overrides
        .route("/createextraservice", get(create_extra_service))
        // Auth endpoints
        .route("/login", get(login_endpoint))
        .route("/login", post(login_endpoint))
        .route("/signup", post(signup_endpoint))
        // Process execution
        .route("/shell_execution", post(shell_execution))
        // RASP endpoints
        .route("/rasp/lfi", get(rasp_lfi))
        .route("/rasp/lfi", post(rasp_lfi))
        .route("/rasp/ssrf", get(rasp_ssrf))
        .route("/rasp/ssrf", post(rasp_ssrf))
        .route("/rasp/sqli", get(rasp_sqli))
        .route("/rasp/sqli", post(rasp_sqli))
        .route("/rasp/multiple", get(rasp_multiple))
        // e2e span endpoints
        .route("/e2e_single_span", get(e2e_single_span))
        .route("/e2e_otel_span", get(e2e_otel_span))
        .route_layer(axum::middleware::from_fn(set_http_route))
        .route_layer(trace::HttpLayer::server(Level::DEBUG))
        .layer(metrics::HttpLayer::server(&meter))
        .into_make_service();

    let listener = tokio::net::TcpListener::bind("0.0.0.0:7777").await.unwrap();
    println!("Listening on port 7777");
    axum::serve(listener, app).await.unwrap();

    meter_provider.shutdown().unwrap();
    tracer_provider.shutdown().unwrap();
}

// tower-otel 0.9.0 declares no "http.route" field in its span macro, so
// span.record("http.route", ...) is a silent no-op even when MatchedPath is
// available. Work around it by setting the attribute directly on the OTel span
// via OpenTelemetrySpanExt::set_attribute, which bypasses the field registry.
async fn set_http_route(
    matched_path: MatchedPath,
    req: Request<axum::body::Body>,
    next: Next,
) -> Response {
    let span = tracing::Span::current();
    span.set_attribute("http.route", matched_path.as_str().to_owned());
    // _dd.top_level marks this as a root span so the library interface can
    // match traces to requests via the user-agent header.
    span.set_attribute("_dd.top_level", 1i64);

    // Set http.url from the request URI + host header (with sensitive params scrubbed)
    let host = req
        .headers()
        .get(axum::http::header::HOST)
        .and_then(|h| h.to_str().ok())
        .unwrap_or("localhost:7777");
    let path = req.uri().path();
    let query_scrubbed = req
        .uri()
        .query()
        .map(scrub_query_string)
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let url = format!("http://{host}{path}{query_scrubbed}");
    span.set_attribute("http.url", url);

    // Set http.referrer_hostname from the Referer header
    if let Some(referer) = req.headers().get(axum::http::header::REFERER) {
        if let Ok(referer_str) = referer.to_str() {
            if let Some(hostname) = extract_hostname_from_referer(referer_str) {
                span.set_attribute("http.referrer_hostname", hostname);
            }
        }
    }

    // Set http.useragent from the User-Agent header
    if let Some(ua) = req.headers().get(axum::http::header::USER_AGENT) {
        if let Ok(ua_str) = ua.to_str() {
            span.set_attribute("http.useragent", ua_str.to_owned());
        }
    }

    // Set http.client_ip from the best IP header available
    if let Some(ip) = extract_client_ip(req.headers()) {
        span.set_attribute("http.client_ip", ip.clone());
        span.set_attribute("network.client.ip", ip);
    }

    next.run(req).await
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
        [
            ("content-type", "text"),
            ("content-language", "en-US"),
        ],
        "Hello headers!\n",
    )
        .into_response()
}

async fn html_endpoint() -> Response {
    let html = "<!DOCTYPE html>\n<html>\n<head>\n    <title>Hello</title>\n</head>\n<body>\n    <h1>Hello</h1>\n</body>\n</html>\n";
    (
        StatusCode::OK,
        [(axum::http::header::CONTENT_TYPE, "text/html")],
        html,
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

async fn flush_endpoint() -> &'static str {
    "flushed"
}

async fn load_dependency() -> &'static str {
    "Loaded"
}

async fn log_library(Query(params): Query<HashMap<String, String>>) -> Response {
    let msg = params.get("msg").cloned().unwrap_or_else(|| "msg".to_string());
    let level = params.get("level").cloned().unwrap_or_else(|| "info".to_string());
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

async fn identify() -> Response {
    let span = tracing::Span::current();
    span.set_attribute("usr.id", "usr.id");
    span.set_attribute("usr.email", "usr.email");
    span.set_attribute("usr.name", "usr.name");
    span.set_attribute("usr.session_id", "usr.session_id");
    span.set_attribute("usr.role", "usr.role");
    span.set_attribute("usr.scope", "usr.scope");
    (StatusCode::OK, "").into_response()
}

async fn identify_propagate() -> Response {
    let span = tracing::Span::current();
    // base64 encoding of "usr.id"
    span.set_attribute("_dd.p.usr_id", "dXNyLmlk");
    (StatusCode::OK, "").into_response()
}

// ─── Path parameter endpoints ─────────────────────────────────────────────────

async fn params_endpoint(Path(_value): Path<String>) -> &'static str {
    "Hello world!\n"
}

async fn sample_rate_route(Path(_i): Path<String>) -> &'static str {
    "Hello world!\n"
}

async fn api_security_sampling_i(Path(i): Path<String>) -> Response {
    let code = i.parse::<u16>().unwrap_or(200);
    let status = StatusCode::from_u16(code).unwrap_or(StatusCode::OK);
    (status, "Hello!\n").into_response()
}

async fn api_security_sampling_standalone(Path(_i): Path<String>) -> &'static str {
    "OK\n"
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
        let span = tracing::info_span!(parent: None, "custom.span");
        let _guard = span.enter();
        let otel_span = tracing::Span::current();
        for i in 0..garbage {
            let tag_key = format!("garbage{i}");
            let tag_val = format!("Random string {i}");
            otel_span.set_attribute(tag_key, tag_val);
        }
    }

    let body = format!("Generated {repeats} spans with {garbage} garbage tags\n");
    (StatusCode::OK, body).into_response()
}

// ─── WAF endpoint ─────────────────────────────────────────────────────────────

async fn waf_endpoint() -> Response {
    (
        StatusCode::OK,
        [(axum::http::header::CONTENT_TYPE, "text/plain")],
        "Hello world!\n",
    )
        .into_response()
}

// ─── Tag value endpoint ────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct TagValuePath {
    tag_value: String,
    status_code: u16,
}

async fn tag_value(
    Path(path): Path<TagValuePath>,
    Query(query_params): Query<HashMap<String, String>>,
    method: Method,
    _headers: HeaderMap,
    body: Bytes,
) -> Response {
    let span = tracing::Span::current();
    span.set_attribute(
        "appsec.events.system_tests_appsec_event.value",
        path.tag_value.clone(),
    );

    let status = StatusCode::from_u16(path.status_code).unwrap_or(StatusCode::OK);

    // Check if the tag_value starts with "payload_in_response_body" and method is POST
    if method == Method::POST && path.tag_value.starts_with("payload_in_response_body") {
        // Try to parse the body as JSON
        let payload: Value = serde_json::from_slice(&body).unwrap_or(Value::Null);
        let mut response_headers = HeaderMap::new();
        for (k, v) in &query_params {
            if let (Ok(name), Ok(val)) = (
                HeaderName::from_str(k),
                HeaderValue::from_str(v),
            ) {
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

// ─── AppSec event tracking ─────────────────────────────────────────────────────

async fn user_login_success_event(Query(params): Query<HashMap<String, String>>) -> Response {
    let user_id = params
        .get("event_user_id")
        .cloned()
        .unwrap_or_else(|| "system_tests_user".to_string());
    let span = tracing::Span::current();
    span.set_attribute("usr.id", user_id);
    span.set_attribute("appsec.events.users.login.success.track", "true");
    span.set_attribute(
        "appsec.events.users.login.success.metadata0",
        "value0",
    );
    span.set_attribute(
        "appsec.events.users.login.success.metadata1",
        "value1",
    );
    (StatusCode::OK, "").into_response()
}

async fn user_login_failure_event(Query(params): Query<HashMap<String, String>>) -> Response {
    let user_id = params
        .get("event_user_id")
        .cloned()
        .unwrap_or_else(|| "system_tests_user".to_string());
    let user_exists = params
        .get("event_user_exists")
        .cloned()
        .unwrap_or_else(|| "true".to_string());
    let span = tracing::Span::current();
    span.set_attribute("usr.id", user_id);
    span.set_attribute("appsec.events.users.login.failure.track", "true");
    span.set_attribute("appsec.events.users.login.failure.usr.exists", user_exists);
    span.set_attribute(
        "appsec.events.users.login.failure.metadata0",
        "value0",
    );
    span.set_attribute(
        "appsec.events.users.login.failure.metadata1",
        "value1",
    );
    (StatusCode::OK, "").into_response()
}

async fn custom_event(Query(params): Query<HashMap<String, String>>) -> Response {
    let event_name = params
        .get("event_name")
        .cloned()
        .unwrap_or_else(|| "system_tests_event".to_string());
    let span = tracing::Span::current();
    span.set_attribute(
        format!("appsec.events.{event_name}.track"),
        "true",
    );
    span.set_attribute(
        format!("appsec.events.{event_name}.metadata0"),
        "value0",
    );
    span.set_attribute(
        format!("appsec.events.{event_name}.metadata1"),
        "value1",
    );
    (StatusCode::OK, "").into_response()
}

#[derive(Deserialize)]
struct UserLoginSuccessV2 {
    login: Option<String>,
    user_id: Option<String>,
    metadata: Option<HashMap<String, Value>>,
}

async fn user_login_success_event_v2(Json(body): Json<UserLoginSuccessV2>) -> Response {
    let span = tracing::Span::current();
    if let Some(user_id) = body.user_id {
        span.set_attribute("usr.id", user_id);
    }
    if let Some(login) = body.login {
        span.set_attribute("usr.login", login);
    }
    span.set_attribute("appsec.events.users.login.success.track", "true");
    if let Some(metadata) = body.metadata {
        for (k, v) in metadata {
            let val = v.as_str().unwrap_or("").to_string();
            span.set_attribute(
                format!("appsec.events.users.login.success.{k}"),
                val,
            );
        }
    }
    (StatusCode::OK, "").into_response()
}

#[derive(Deserialize)]
struct UserLoginFailureV2 {
    login: Option<String>,
    exists: Option<String>,
    metadata: Option<HashMap<String, Value>>,
}

async fn user_login_failure_event_v2(Json(body): Json<UserLoginFailureV2>) -> Response {
    let span = tracing::Span::current();
    if let Some(login) = body.login {
        span.set_attribute("usr.login", login);
    }
    span.set_attribute("appsec.events.users.login.failure.track", "true");
    if let Some(exists) = body.exists {
        span.set_attribute("appsec.events.users.login.failure.usr.exists", exists);
    }
    if let Some(metadata) = body.metadata {
        for (k, v) in metadata {
            let val = v.as_str().unwrap_or("").to_string();
            span.set_attribute(
                format!("appsec.events.users.login.failure.{k}"),
                val,
            );
        }
    }
    (StatusCode::OK, "").into_response()
}

// ─── AppSec blocking ──────────────────────────────────────────────────────────

async fn users_endpoint(Query(params): Query<HashMap<String, String>>) -> Response {
    let user = params.get("user").cloned().unwrap_or_default();
    let span = tracing::Span::current();
    span.set_attribute("usr.id", user.clone());
    // In real implementation, the tracer would block here if the WAF says so.
    (StatusCode::OK, format!("Hello, user {user}!")).into_response()
}

// ─── Headers / returnheaders endpoints ───────────────────────────────────────

async fn return_headers(request: Request) -> Json<Value> {
    let mut headers_map = serde_json::Map::new();
    for (name, value) in request.headers() {
        if let Ok(v) = value.to_str() {
            headers_map.insert(name.as_str().to_string(), json!(v));
        }
    }
    Json(json!(headers_map))
}

async fn request_downstream() -> Json<Value> {
    let client = reqwest::Client::new();
    match client
        .get("http://weblog:7777/returnheaders")
        .send()
        .await
    {
        Ok(resp) => {
            let body: Value = resp.json().await.unwrap_or(Value::Null);
            Json(body)
        }
        Err(_) => Json(json!({})),
    }
}

async fn vulnerable_request_downstream() -> Json<Value> {
    let client = reqwest::Client::new();
    match client
        .get("http://weblog:7777/returnheaders")
        .send()
        .await
    {
        Ok(resp) => {
            let body: Value = resp.json().await.unwrap_or(Value::Null);
            Json(body)
        }
        Err(_) => Json(json!({})),
    }
}

// ─── Cookie / session endpoints ───────────────────────────────────────────────

async fn set_cookie(Query(params): Query<HashMap<String, String>>) -> Response {
    let name = params.get("name").cloned().unwrap_or_default();
    let value = params.get("value").cloned().unwrap_or_default();
    let cookie_val = format!("{name}={value}");
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(&cookie_val) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn session_new() -> Response {
    let session_id = uuid::Uuid::new_v4().to_string();
    let cookie_val = format!("session_id={session_id}; Path=/");
    let mut resp = (StatusCode::OK, session_id).into_response();
    if let Ok(v) = HeaderValue::from_str(&cookie_val) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

// ─── External request endpoints ───────────────────────────────────────────────

async fn make_distant_call(Query(params): Query<HashMap<String, String>>) -> Response {
    let url = params.get("url").cloned().unwrap_or_default();
    let host = reqwest::Url::parse(&url)
        .ok()
        .and_then(|u| u.host_str().map(str::to_owned))
        .unwrap_or_default();

    let span = tracing::info_span!(
        "http.client.request",
        "otel.kind" = "client",
        "http.request.method" = "GET",
        "server.address" = %host,
        "out.host" = %host,
        "network.protocol.name" = "http",
        "http.response.status_code" = tracing::field::Empty,
    );

    let resp = reqwest::Client::new()
        .get(&url)
        .send()
        .instrument(span.clone())
        .await;

    match resp {
        Ok(r) => {
            span.record("http.response.status_code", r.status().as_u16());
            Json(json!({
                "url": url,
                "status_code": r.status().as_u16(),
                "request_headers": {},
                "response_headers": {}
            }))
            .into_response()
        }
        Err(e) => {
            tracing::warn!("make_distant_call failed: {e}");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

async fn external_request(method: Method, request: Request) -> Response {
    let (parts, body_bytes) = {
        let (parts, body) = request.into_parts();
        let bytes = axum::body::to_bytes(body, usize::MAX)
            .await
            .unwrap_or_default();
        (parts, bytes)
    };

    let query_params: HashMap<String, String> = parts
        .uri
        .query()
        .map(|q| {
            url::form_urlencoded::parse(q.as_bytes())
                .into_owned()
                .collect()
        })
        .unwrap_or_default();

    let status_code = query_params.get("status").cloned().unwrap_or_else(|| "200".to_string());
    let url_extra = query_params.get("url_extra").cloned().unwrap_or_default();

    let target_url = format!("http://internal_server:8089/mirror/{status_code}{url_extra}");

    let client = reqwest::Client::new();
    let mut req_builder = client.request(
        reqwest::Method::from_bytes(method.as_str().as_bytes()).unwrap_or(reqwest::Method::GET),
        &target_url,
    );

    // Forward query params as headers (except status and url_extra)
    for (k, v) in &query_params {
        if k != "status" && k != "url_extra" {
            if let Ok(name) = reqwest::header::HeaderName::from_str(k) {
                if let Ok(val) = reqwest::header::HeaderValue::from_str(v) {
                    req_builder = req_builder.header(name, val);
                }
            }
        }
    }

    // Forward body with content-type if present
    if !body_bytes.is_empty() {
        if let Some(ct) = parts.headers.get(axum::http::header::CONTENT_TYPE) {
            if let Ok(ct_str) = ct.to_str() {
                if let Ok(name) = reqwest::header::HeaderName::from_str("content-type") {
                    if let Ok(val) = reqwest::header::HeaderValue::from_str(ct_str) {
                        req_builder = req_builder.header(name, val);
                    }
                }
            }
        }
        req_builder = req_builder.body(body_bytes.to_vec());
    }

    match req_builder.send().await {
        Ok(resp) => {
            let status = resp.status().as_u16();
            let resp_headers: HashMap<String, String> = resp
                .headers()
                .iter()
                .filter_map(|(k, v)| v.to_str().ok().map(|v| (k.as_str().to_string(), v.to_string())))
                .collect();
            match resp.json::<Value>().await {
                Ok(payload) => Json(json!({
                    "status": status,
                    "payload": payload,
                    "headers": resp_headers,
                }))
                .into_response(),
                Err(e) => Json(json!({
                    "status": status as i64,
                    "error": format!("Failed to parse response: {e}"),
                }))
                .into_response(),
            }
        }
        Err(e) => Json(json!({
            "status": null,
            "error": format!("{e}"),
        }))
        .into_response(),
    }
}

async fn external_request_redirect(Query(params): Query<HashMap<String, String>>) -> Response {
    let total_redirects: u32 = params
        .get("totalRedirects")
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);

    let client = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::limited(20))
        .build()
        .unwrap_or_default();

    let url = format!(
        "http://internal_server:8089/redirect?totalRedirects={total_redirects}"
    );

    match client.get(&url).send().await {
        Ok(_) => (StatusCode::OK, "").into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("error: {e}"),
        )
            .into_response(),
    }
}

// ─── Inferred proxy span ──────────────────────────────────────────────────────

async fn inferred_proxy_span_creation(
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let status_code: u16 = params
        .get("status_code")
        .and_then(|v| v.parse().ok())
        .unwrap_or(200);

    // Set inferred proxy span attributes if headers are present
    let span = tracing::Span::current();
    if let Some(proxy) = headers.get("x-dd-proxy") {
        if let Ok(proxy_str) = proxy.to_str() {
            span.set_attribute("_dd.inferred_span.tag_source", "self");
            span.set_attribute("x-dd-proxy", proxy_str.to_string());
        }
    }

    let status = StatusCode::from_u16(status_code).unwrap_or(StatusCode::OK);
    (status, "").into_response()
}

// ─── Service override ─────────────────────────────────────────────────────────

async fn create_extra_service(Query(params): Query<HashMap<String, String>>) -> Response {
    let service_name = params.get("serviceName").cloned().unwrap_or_default();
    let span = tracing::Span::current();
    span.set_attribute("service.name", service_name.clone());
    span.set_attribute("service", service_name);
    (StatusCode::OK, "").into_response()
}

// ─── Auth endpoints ────────────────────────────────────────────────────────────

async fn login_endpoint(
    Query(_params): Query<HashMap<String, String>>,
    _request: Request,
) -> Response {
    // Stub: always succeed with basic user
    let span = tracing::Span::current();
    span.set_attribute("usr.id", "test_user");
    (StatusCode::OK, "").into_response()
}

async fn signup_endpoint(
    Query(_params): Query<HashMap<String, String>>,
    _request: Request,
) -> Response {
    // Stub: always succeed
    (StatusCode::OK, "").into_response()
}

// ─── Shell execution endpoint ──────────────────────────────────────────────────

#[derive(Deserialize)]
struct ShellExecutionBody {
    command: Option<Value>,
    options: Option<HashMap<String, Value>>,
    args: Option<Vec<String>>,
}

async fn shell_execution(Json(body): Json<ShellExecutionBody>) -> Response {
    let use_shell = body
        .options
        .as_ref()
        .and_then(|o| o.get("shell"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let cmd_str = match &body.command {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Array(arr)) => arr
            .first()
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        _ => return (StatusCode::BAD_REQUEST, "missing command").into_response(),
    };

    let args: Vec<String> = body.args.unwrap_or_default();

    let result = if use_shell {
        std::process::Command::new("sh")
            .arg("-c")
            .arg(&cmd_str)
            .args(&args)
            .output()
    } else {
        std::process::Command::new(&cmd_str).args(&args).output()
    };

    match result {
        Ok(_) => (StatusCode::OK, "").into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, format!("{e}")).into_response(),
    }
}

// ─── RASP endpoints ───────────────────────────────────────────────────────────

async fn rasp_lfi(
    method: Method,
    Query(query_params): Query<HashMap<String, String>>,
    body: Bytes,
) -> Response {
    let file = if method == Method::GET {
        query_params.get("file").cloned().unwrap_or_default()
    } else {
        // Try to parse body as JSON, form, or XML
        parse_file_from_body(&body)
    };

    // Perform the file operation (the tracer intercepts this for RASP)
    let _ = std::fs::metadata(&file);
    (StatusCode::OK, format!("file: {file}")).into_response()
}

fn parse_file_from_body(body: &Bytes) -> String {
    // Try JSON first
    if let Ok(v) = serde_json::from_slice::<Value>(body) {
        if let Some(f) = v.get("file").and_then(|f| f.as_str()) {
            return f.to_string();
        }
    }
    // Try form-urlencoded
    for (k, v) in url::form_urlencoded::parse(body) {
        if k == "file" {
            return v.to_string();
        }
    }
    String::new()
}

async fn rasp_ssrf(
    method: Method,
    Query(query_params): Query<HashMap<String, String>>,
    body: Bytes,
) -> Response {
    let domain = if method == Method::GET {
        query_params.get("domain").cloned().unwrap_or_default()
    } else {
        parse_domain_from_body(&body)
    };

    // Perform the network operation (the tracer intercepts this for RASP)
    let url = format!("http://{domain}");
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(1))
        .build()
        .unwrap_or_default();
    let _ = client.get(&url).send().await;

    (StatusCode::OK, format!("domain: {domain}")).into_response()
}

fn parse_domain_from_body(body: &Bytes) -> String {
    if let Ok(v) = serde_json::from_slice::<Value>(body) {
        if let Some(d) = v.get("domain").and_then(|d| d.as_str()) {
            return d.to_string();
        }
    }
    for (k, v) in url::form_urlencoded::parse(body) {
        if k == "domain" {
            return v.to_string();
        }
    }
    String::new()
}

// Simulates a SQL query span for client-side stats obfuscation testing.
async fn rasp_sqli(
    Query(_params): Query<HashMap<String, String>>,
    _body: Bytes,
) -> Response {
    let _guard = tracing::info_span!(
        parent: None,
        "sqlite.query",
        "otel.kind" = "client",
        "db.system" = "sqlite",
        "db.statement" = "SELECT * FROM users WHERE id = ?",
    )
    .entered();
    StatusCode::OK.into_response()
}

async fn rasp_multiple(Query(params): Query<HashMap<String, String>>) -> Response {
    let file1 = params.get("file1").cloned().unwrap_or_default();
    let file2 = params.get("file2").cloned().unwrap_or_default();

    let _ = std::fs::metadata(&file1);
    let _ = std::fs::metadata(&file2);
    let _ = std::fs::metadata("../etc/passwd");

    (StatusCode::OK, "").into_response()
}

// ─── e2e span endpoints ───────────────────────────────────────────────────────

async fn e2e_single_span(Query(params): Query<HashMap<String, String>>) -> Response {
    let parent_name = params.get("parentName").cloned().unwrap_or_default();
    let child_name = params.get("childName").cloned().unwrap_or_default();
    let should_index = params.get("shouldIndex").cloned().unwrap_or_default();

    let parent_span = tracing::info_span!(
        parent: None,
        "e2e.single.span",
        "span.name" = %parent_name,
    );

    {
        let _guard = parent_span.enter();
        let otel_span = tracing::Span::current();
        if should_index == "1" {
            otel_span.set_attribute("_dd.filter.kept", 1i64);
            otel_span.set_attribute("manual.keep", "true");
        }

        let child_span = tracing::info_span!("e2e.child.span", "span.name" = %child_name);
        let _child_guard = child_span.enter();
        if should_index == "1" {
            tracing::Span::current().set_attribute("_dd.filter.kept", 1i64);
            tracing::Span::current().set_attribute("manual.keep", "true");
        }
    }

    (StatusCode::OK, "").into_response()
}

async fn e2e_otel_span(Query(params): Query<HashMap<String, String>>) -> Response {
    use opentelemetry::trace::{Tracer, TraceContextExt, SpanKind, Span as OtelSpan};
    use opentelemetry::{KeyValue, Context};

    let parent_name = params.get("parentName").cloned().unwrap_or_default();
    let child_name = params.get("childName").cloned().unwrap_or_default();
    let should_index = params.get("shouldIndex").cloned().unwrap_or_default();

    let tracer = opentelemetry::global::tracer("e2e_otel");

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
