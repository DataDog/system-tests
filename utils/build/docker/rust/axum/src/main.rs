use std::collections::HashMap;
use std::str::FromStr as _;
use std::sync::OnceLock;

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

/// Single runtime-id for the lifetime of this process.
static RUNTIME_ID: OnceLock<String> = OnceLock::new();
fn runtime_id() -> &'static str {
    RUNTIME_ID.get_or_init(|| uuid::Uuid::new_v4().to_string())
}

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
        .route("/read_file", get(read_file))
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
        // SQLi + endpoint_fallback
        .route("/sqli", get(sqli_endpoint))
        .route("/endpoint_fallback", get(endpoint_fallback))
        // RASP: shell injection + command injection
        .route("/rasp/shi", get(rasp_shi))
        .route("/rasp/shi", post(rasp_shi))
        .route("/rasp/cmdi", get(rasp_cmdi))
        .route("/rasp/cmdi", post(rasp_cmdi))
        // IAST cookie endpoints
        .route("/iast/insecure-cookie/test_secure", get(iast_insecure_cookie_test_secure))
        .route("/iast/insecure-cookie/test_insecure", get(iast_insecure_cookie_test_insecure))
        .route("/iast/insecure-cookie/custom_cookie", post(iast_insecure_cookie_custom_cookie))
        .route("/iast/insecure-cookie/test_empty_cookie", get(iast_insecure_cookie_test_empty_cookie))
        .route("/iast/no-httponly-cookie/test_secure", get(iast_no_httponly_cookie_test_secure))
        .route("/iast/no-httponly-cookie/test_insecure", get(iast_no_httponly_cookie_test_insecure))
        .route("/iast/no-httponly-cookie/test_empty_cookie", get(iast_no_httponly_cookie_test_empty_cookie))
        .route("/iast/no-httponly-cookie/custom_cookie", post(iast_no_httponly_cookie_custom_cookie))
        .route("/iast/no-samesite-cookie/test_secure", get(iast_no_samesite_cookie_test_secure))
        .route("/iast/no-samesite-cookie/test_insecure", get(iast_no_samesite_cookie_test_insecure))
        .route("/iast/no-samesite-cookie/test_empty_cookie", get(iast_no_samesite_cookie_test_empty_cookie))
        .route("/iast/no-samesite-cookie/custom_cookie", post(iast_no_samesite_cookie_custom_cookie))
        // IAST hashing / secrets / header injection / sampling
        .route("/iast/insecure_hashing/deduplicate", get(iast_insecure_hashing_deduplicate))
        .route("/iast/insecure_hashing/multiple_hash", get(iast_insecure_hashing_multiple_hash))
        .route("/iast/insecure_hashing/test_secure_algorithm", get(iast_insecure_hashing_secure))
        .route("/iast/insecure_hashing/test_md5_algorithm", get(iast_insecure_hashing_md5))
        .route("/iast/hardcoded_secrets/test_insecure", get(iast_hardcoded_secrets))
        .route("/iast/header_injection/reflected/exclusion", get(iast_header_injection_exclusion))
        .route("/iast/header_injection/reflected/no-exclusion", get(iast_header_injection_no_exclusion))
        .route("/iast/sampling-by-route-method-count/{key}", get(iast_sampling_count))
        .route("/iast/sampling-by-route-method-count/{key}", post(iast_sampling_count_post))
        .route("/iast/sampling-by-route-method-count-2/{key}", get(iast_sampling_count_2))
        // IAST source endpoints
        .route("/iast/source/parameter/test", get(iast_source_parameter_get))
        .route("/iast/source/parameter/test", post(iast_source_parameter_post))
        .route("/iast/source/parametername/test", get(iast_source_parametername_get))
        .route("/iast/source/parametername/test", post(iast_source_parametername_post))
        .route("/iast/source/header/test", get(iast_source_header))
        .route("/iast/source/headername/test", get(iast_source_headername))
        .route("/iast/source/cookievalue/test", get(iast_source_cookievalue))
        .route("/iast/source/cookiename/test", get(iast_source_cookiename))
        .route("/iast/source/multipart/test", post(iast_source_multipart))
        .route("/iast/source/body/test", post(iast_source_body))
        .route("/iast/source/sql/test", get(iast_source_sql))
        // IAST SC (security controls)
        .route("/iast/sc/s/configured", post(iast_sc_s_configured))
        .route("/sc/s/not-configured", post(iast_sc_s_not_configured))
        .route("/sc/s/all", post(iast_sc_s_all))
        .route("/sc/iv/configured", post(iast_sc_iv_configured))
        .route("/sc/iv/not-configured", post(iast_sc_iv_not_configured))
        .route("/sc/iv/all", post(iast_sc_iv_all))
        .route("/sc/iv/overloaded/secure", post(iast_sc_iv_overloaded_secure))
        .route("/sc/iv/overloaded/insecure", post(iast_sc_iv_overloaded_insecure))
        .route("/sc/s/overloaded/secure", post(iast_sc_s_overloaded_secure))
        .route("/sc/s/overloaded/insecure", post(iast_sc_s_overloaded_insecure))
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
    // Capture for post-response error tagging
    let span_before = tracing::Span::current();
    let span = tracing::Span::current();
    span.set_attribute("http.route", matched_path.as_str().to_owned());
    // _dd.top_level marks this as a root span so the library interface can
    // match traces to requests via the user-agent header.
    span.set_attribute("_dd.top_level", 1i64);
    // Datadog semantic-convention tags required by system-tests.
    span.set_attribute("language", "rust");
    span.set_attribute("component", "axum");
    span.set_attribute("runtime-id", runtime_id());
    // process_id goes to the metrics map (numeric value).
    span.set_attribute("process_id", std::process::id() as i64);

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

    let response = next.run(req).await;
    // Mark 5xx server errors on the span
    let status = response.status();
    if status.is_server_error() {
        span_before.set_status(opentelemetry::trace::Status::Error {
            description: format!("HTTP {}", status.as_u16()).into(),
        });
    }
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

/// Add Datadog semantic tags to the *current* tracing span.
/// Call this inside any manually-created span to keep validate_all_spans happy.
fn add_dd_tags() {
    let span = tracing::Span::current();
    span.set_attribute("language", "rust");
    span.set_attribute("component", "axum");
    span.set_attribute("runtime-id", runtime_id());
    span.set_attribute("process_id", std::process::id() as i64);
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

async fn read_file(Query(params): Query<HashMap<String, String>>) -> Response {
    let file = params.get("file").cloned().unwrap_or_default();
    match std::fs::read_to_string(&file) {
        Ok(content) => (StatusCode::OK, content).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Error: {e}")).into_response(),
    }
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
    span.set_attribute("usr.id", "usr.id");
    span.set_attribute("_dd.p.usr.id", "dXNyLmlk");
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
        add_dd_tags();
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
    let parsed = reqwest::Url::parse(&url).ok();
    let host = parsed
        .as_ref()
        .and_then(|u| u.host_str().map(str::to_owned))
        .unwrap_or_default();

    // Build scrubbed URL for the client span's http.url tag (preserving port)
    let scrubbed_url = parsed.as_ref().map(|u| {
        let path = u.path();
        let query_scrubbed = u.query().map(scrub_query_string);
        let qs = query_scrubbed.as_deref().map(|q| format!("?{q}")).unwrap_or_default();
        let host_port = match u.port() {
            Some(p) => format!("{}:{}", u.host_str().unwrap_or(""), p),
            None => u.host_str().unwrap_or("").to_string(),
        };
        format!("{}://{}{}{}", u.scheme(), host_port, path, qs)
    }).unwrap_or_else(|| url.clone());

    let span = tracing::info_span!(
        "http.client.request",
        "otel.kind" = "client",
        "http.request.method" = "GET",
        "server.address" = %host,
        "out.host" = %host,
        "network.protocol.name" = "http",
        "http.response.status_code" = tracing::field::Empty,
    );
    span.in_scope(|| {
        add_dd_tags();
        tracing::Span::current().set_attribute("http.url", scrubbed_url.clone());
        tracing::Span::current().set_attribute("span.kind", "client");
    });

    let resp = reqwest::Client::new()
        .get(&url)
        .send()
        .instrument(span.clone())
        .await;

    match resp {
        Ok(r) => {
            let status = r.status().as_u16();
            span.in_scope(|| {
                let s = tracing::Span::current();
                // Set as both string (meta) and int (metrics) for compatibility
                s.set_attribute("http.status_code", status.to_string());
                s.set_attribute("http.response.status_code", status as i64);
                if status >= 400 {
                    s.set_attribute("error.type", "HTTP Error");
                    // Set OTel span status to Error — translated to error:1 by datadog-opentelemetry
                    s.set_status(opentelemetry::trace::Status::Error {
                        description: format!("HTTP {status}").into(),
                    });
                }
            });
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
    add_dd_tags();
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
// ─── chunk A: sqli, endpoint_fallback, rasp/shi, rasp/cmdi ───────────────────

async fn sqli_endpoint(Query(params): Query<HashMap<String, String>>) -> Response {
    use rusqlite::Connection;

    let q = params.get("q").cloned().unwrap_or_default();

    let conn = match Connection::open_in_memory() {
        Ok(c) => c,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, format!("DB error: {e}")).into_response(),
    };

    // Create users table with sample data
    let setup = conn.execute_batch(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);
         INSERT INTO users VALUES (1, 'Alice', 'alice@example.com');
         INSERT INTO users VALUES (2, 'Bob', 'bob@example.com');
         INSERT INTO users VALUES (3, 'Carol', 'carol@example.com');",
    );
    if let Err(e) = setup {
        return (StatusCode::INTERNAL_SERVER_ERROR, format!("Setup error: {e}")).into_response();
    }

    // Unsafe injection: q is interpolated directly into the query string
    let query = format!("SELECT * FROM users WHERE id='{q}'");
    let mut stmt = match conn.prepare(&query) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, format!("Query error: {e}")).into_response(),
    };

    let rows: Vec<String> = match stmt.query_map([], |row| {
        let id: i64 = row.get(0)?;
        let name: String = row.get(1)?;
        let email: String = row.get(2)?;
        Ok(format!("{id}|{name}|{email}"))
    }) {
        Ok(mapped) => mapped.filter_map(|r| r.ok()).collect(),
        Err(_) => Vec::new(),
    };

    (StatusCode::OK, rows.join("\n")).into_response()
}

async fn endpoint_fallback(Query(params): Query<HashMap<String, String>>) -> Response {
    let case = params.get("case").cloned().unwrap_or_default();
    let span = tracing::Span::current();

    match case.as_str() {
        "with_route" => {
            span.set_attribute("http.route", "/users/{id}/profile".to_owned());
            (StatusCode::OK, "").into_response()
        }
        "with_endpoint" => {
            span.set_attribute("http.endpoint", "/api/products/{param:int}".to_owned());
            (StatusCode::OK, "").into_response()
        }
        "404" => {
            span.set_attribute("http.endpoint", "/api/notfound/{param:int}".to_owned());
            (StatusCode::NOT_FOUND, "").into_response()
        }
        "computed" => {
            span.set_attribute(
                "http.url",
                "http://localhost:8080/endpoint_fallback_computed/users/123/orders/456".to_owned(),
            );
            (StatusCode::OK, "").into_response()
        }
        _ => (StatusCode::OK, "").into_response(),
    }
}

fn parse_list_dir_from_body(body: &Bytes) -> String {
    // Try JSON first
    if let Ok(v) = serde_json::from_slice::<Value>(body) {
        if let Some(d) = v.get("list_dir").and_then(|d| d.as_str()) {
            return d.to_string();
        }
    }
    // Try form-urlencoded
    for (k, v) in url::form_urlencoded::parse(body) {
        if k == "list_dir" {
            return v.to_string();
        }
    }
    // Try XML: extract <list_dir>value</list_dir>
    let body_str = std::str::from_utf8(body).unwrap_or("");
    if let Some(start) = body_str.find("<list_dir>") {
        let after = &body_str[start + "<list_dir>".len()..];
        if let Some(end) = after.find("</list_dir>") {
            return after[..end].to_string();
        }
    }
    String::new()
}

async fn rasp_shi(
    method: Method,
    Query(query_params): Query<HashMap<String, String>>,
    body: Bytes,
) -> Response {
    let list_dir = if method == Method::GET {
        query_params.get("list_dir").cloned().unwrap_or_default()
    } else {
        parse_list_dir_from_body(&body)
    };

    // Shell injection: the tracer will intercept this for RASP
    let result = std::process::Command::new("sh")
        .arg("-c")
        .arg(format!("ls {list_dir}"))
        .output();

    match result {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            (StatusCode::OK, stdout).into_response()
        }
        Err(e) => (StatusCode::OK, format!("error: {e}")).into_response(),
    }
}

fn parse_command_from_body(body: &Bytes) -> (String, Vec<String>) {
    // Try JSON first
    if let Ok(v) = serde_json::from_slice::<Value>(body) {
        match v.get("command") {
            Some(Value::Array(arr)) => {
                let parts: Vec<String> = arr
                    .iter()
                    .filter_map(|x| x.as_str().map(str::to_string))
                    .collect();
                if let Some((cmd, rest)) = parts.split_first() {
                    return (cmd.clone(), rest.to_vec());
                }
            }
            Some(Value::String(s)) => {
                let mut parts = s.split_whitespace();
                let cmd = parts.next().unwrap_or("").to_string();
                let args: Vec<String> = parts.map(str::to_string).collect();
                return (cmd, args);
            }
            _ => {}
        }
    }
    // Try form-urlencoded
    for (k, v) in url::form_urlencoded::parse(body) {
        if k == "command" {
            let mut parts = v.split_whitespace();
            let cmd = parts.next().unwrap_or("").to_string();
            let args: Vec<String> = parts.map(str::to_string).collect();
            return (cmd, args);
        }
    }
    // Try XML: extract <command>value</command>
    let body_str = std::str::from_utf8(body).unwrap_or("");
    if let Some(start) = body_str.find("<command>") {
        let after = &body_str[start + "<command>".len()..];
        if let Some(end) = after.find("</command>") {
            let raw = &after[..end];
            let mut parts = raw.split_whitespace();
            let cmd = parts.next().unwrap_or("").to_string();
            let args: Vec<String> = parts.map(str::to_string).collect();
            return (cmd, args);
        }
    }
    (String::new(), Vec::new())
}

async fn rasp_cmdi(
    method: Method,
    Query(query_params): Query<HashMap<String, String>>,
    body: Bytes,
) -> Response {
    let (cmd, args) = if method == Method::GET {
        let command_str = query_params.get("command").cloned().unwrap_or_default();
        let mut parts = command_str.split_whitespace();
        let cmd = parts.next().unwrap_or("").to_string();
        let args: Vec<String> = parts.map(str::to_string).collect();
        (cmd, args)
    } else {
        parse_command_from_body(&body)
    };

    if cmd.is_empty() {
        return (StatusCode::OK, "no command provided").into_response();
    }

    // Command injection without shell: the tracer will intercept for RASP
    let result = std::process::Command::new(&cmd).args(&args).output();

    match result {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            (StatusCode::OK, stdout).into_response()
        }
        Err(e) => (StatusCode::OK, format!("error: {e}")).into_response(),
    }
}
// ─── chunk B: IAST cookie endpoints ──────────────────────────────────────────

#[derive(Deserialize)]
struct CookieBody {
    #[serde(rename = "cookieName")]
    cookie_name: String,
    #[serde(rename = "cookieValue")]
    cookie_value: String,
}

// ─── /iast/insecure-cookie ────────────────────────────────────────────────────

async fn iast_insecure_cookie_test_secure() -> Response {
    let cookie_str = "test=secure_value; Secure; HttpOnly; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_insecure_cookie_test_insecure() -> Response {
    let cookie_str = "insecure_cookie=insecure_value; HttpOnly; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_insecure_cookie_custom_cookie(Json(body): Json<CookieBody>) -> Response {
    let cookie_str = format!(
        "{}={}; HttpOnly; SameSite=Strict",
        body.cookie_name, body.cookie_value
    );
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(&cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_insecure_cookie_test_empty_cookie() -> Response {
    let cookie_str = "empty_cookie=; HttpOnly; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

// ─── /iast/no-httponly-cookie ─────────────────────────────────────────────────

async fn iast_no_httponly_cookie_test_secure() -> Response {
    let cookie_str = "test=secure_value; Secure; HttpOnly; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_no_httponly_cookie_test_insecure() -> Response {
    let cookie_str = "no_httponly_cookie=insecure_value; Secure; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_no_httponly_cookie_test_empty_cookie() -> Response {
    let cookie_str = "empty_cookie=; Secure; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_no_httponly_cookie_custom_cookie(Json(body): Json<CookieBody>) -> Response {
    let cookie_str = format!(
        "{}={}; Secure; SameSite=Strict",
        body.cookie_name, body.cookie_value
    );
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(&cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

// ─── /iast/no-samesite-cookie ─────────────────────────────────────────────────

async fn iast_no_samesite_cookie_test_secure() -> Response {
    let cookie_str = "test=secure_value; Secure; HttpOnly; SameSite=Strict";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_no_samesite_cookie_test_insecure() -> Response {
    let cookie_str = "no_samesite_cookie=insecure_value; Secure; HttpOnly";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_no_samesite_cookie_test_empty_cookie() -> Response {
    let cookie_str = "empty_cookie=; Secure; HttpOnly";
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}

async fn iast_no_samesite_cookie_custom_cookie(Json(body): Json<CookieBody>) -> Response {
    let cookie_str = format!(
        "{}={}; Secure; HttpOnly",
        body.cookie_name, body.cookie_value
    );
    let mut resp = (StatusCode::OK, "").into_response();
    if let Ok(v) = HeaderValue::from_str(&cookie_str) {
        resp.headers_mut().insert("set-cookie", v);
    }
    resp
}
// ─── chunk C: IAST hashing/secrets/header-injection/sampling ─────────────────

async fn iast_insecure_hashing_deduplicate() -> Response {
    for _ in 0..2 {
        let _ = md5::compute("test_string");
        let _ = md5::compute("test_string");
    }
    (StatusCode::OK, "deduplicate").into_response()
}

async fn iast_insecure_hashing_multiple_hash() -> Response {
    // First insecure hash: MD5
    let _ = md5::compute("multiple_hash_input");

    // Second insecure hash: std DefaultHasher (different algorithm, different line)
    {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        let mut hasher = DefaultHasher::new();
        "multiple_hash_input".hash(&mut hasher);
        let _ = hasher.finish();
    }

    (StatusCode::OK, "multiple_hash").into_response()
}

async fn iast_insecure_hashing_secure() -> Response {
    use sha2::{Digest, Sha256};
    let _ = Sha256::digest(b"secure_data");
    (StatusCode::OK, "secure").into_response()
}

async fn iast_insecure_hashing_md5() -> Response {
    let _ = md5::compute("md5_input");
    (StatusCode::OK, "md5").into_response()
}

async fn iast_hardcoded_secrets() -> Response {
    let _secret = "hardcoded_secret_value_12345";
    (StatusCode::OK, "hardcoded").into_response()
}

async fn iast_header_injection_exclusion(
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let reflected_name = params.get("reflected").cloned().unwrap_or_default();
    let origin_name = params.get("origin").cloned().unwrap_or_default();

    let origin_value = headers
        .get(&origin_name)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_owned();

    let mut resp = (StatusCode::OK, "reflected").into_response();
    if let (Ok(name), Ok(val)) = (
        HeaderName::from_str(&reflected_name),
        HeaderValue::from_str(&origin_value),
    ) {
        resp.headers_mut().insert(name, val);
    }
    resp
}

async fn iast_header_injection_no_exclusion(
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let header_to_reflect = params.get("reflected").cloned().unwrap_or_default();
    let header_origin = params.get("origin").cloned().unwrap_or_default();

    let value_from_request = headers
        .get(&header_origin)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_owned();

    let mut response = (StatusCode::OK, "reflected").into_response();
    if let (Ok(name), Ok(val)) = (
        HeaderName::from_str(&header_to_reflect),
        HeaderValue::from_str(&value_from_request),
    ) {
        response.headers_mut().insert(name, val);
    }
    response
}

async fn iast_sampling_count(Path(_key): Path<String>) -> Response {
    // 15 distinct MD5 vulnerable operations on separate lines for IAST sampling
    let _h1  = md5::compute("sampling_input_1");
    let _h2  = md5::compute("sampling_input_2");
    let _h3  = md5::compute("sampling_input_3");
    let _h4  = md5::compute("sampling_input_4");
    let _h5  = md5::compute("sampling_input_5");
    let _h6  = md5::compute("sampling_input_6");
    let _h7  = md5::compute("sampling_input_7");
    let _h8  = md5::compute("sampling_input_8");
    let _h9  = md5::compute("sampling_input_9");
    let _h10 = md5::compute("sampling_input_10");
    let _h11 = md5::compute("sampling_input_11");
    let _h12 = md5::compute("sampling_input_12");
    let _h13 = md5::compute("sampling_input_13");
    let _h14 = md5::compute("sampling_input_14");
    let _h15 = md5::compute("sampling_input_15");
    (StatusCode::OK, "15 vulnerabilities").into_response()
}

async fn iast_sampling_count_post(Path(_key): Path<String>) -> Response {
    // 15 distinct MD5 vulnerable operations on separate lines for IAST sampling (POST)
    let _h1  = md5::compute("post_sampling_input_1");
    let _h2  = md5::compute("post_sampling_input_2");
    let _h3  = md5::compute("post_sampling_input_3");
    let _h4  = md5::compute("post_sampling_input_4");
    let _h5  = md5::compute("post_sampling_input_5");
    let _h6  = md5::compute("post_sampling_input_6");
    let _h7  = md5::compute("post_sampling_input_7");
    let _h8  = md5::compute("post_sampling_input_8");
    let _h9  = md5::compute("post_sampling_input_9");
    let _h10 = md5::compute("post_sampling_input_10");
    let _h11 = md5::compute("post_sampling_input_11");
    let _h12 = md5::compute("post_sampling_input_12");
    let _h13 = md5::compute("post_sampling_input_13");
    let _h14 = md5::compute("post_sampling_input_14");
    let _h15 = md5::compute("post_sampling_input_15");
    (StatusCode::OK, "15 vulnerabilities").into_response()
}

async fn iast_sampling_count_2(Path(_key): Path<String>) -> Response {
    // 15 distinct MD5 vulnerable operations — different inputs from iast_sampling_count
    let _a1  = md5::compute("route2_alpha_001");
    let _a2  = md5::compute("route2_alpha_002");
    let _a3  = md5::compute("route2_alpha_003");
    let _a4  = md5::compute("route2_alpha_004");
    let _a5  = md5::compute("route2_alpha_005");
    let _a6  = md5::compute("route2_alpha_006");
    let _a7  = md5::compute("route2_alpha_007");
    let _a8  = md5::compute("route2_alpha_008");
    let _a9  = md5::compute("route2_alpha_009");
    let _a10 = md5::compute("route2_alpha_010");
    let _a11 = md5::compute("route2_alpha_011");
    let _a12 = md5::compute("route2_alpha_012");
    let _a13 = md5::compute("route2_alpha_013");
    let _a14 = md5::compute("route2_alpha_014");
    let _a15 = md5::compute("route2_alpha_015");
    (StatusCode::OK, "15 vulnerabilities").into_response()
}
// ─── IAST source endpoints ────────────────────────────────────────────────────

/// GET /iast/source/parameter/test
/// Tainted source: query param value
async fn iast_source_parameter_get(
    Query(params): Query<HashMap<String, String>>,
) -> Response {
    let table = params.get("table").cloned().unwrap_or_default();
    let _ = md5::compute(table.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /iast/source/parameter/test
/// Tainted source: form-urlencoded body param value
async fn iast_source_parameter_post(body: Bytes) -> Response {
    let table = url::form_urlencoded::parse(&body)
        .find(|(k, _)| k == "table")
        .map(|(_, v)| v.into_owned())
        .unwrap_or_default();
    let _ = md5::compute(table.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// GET /iast/source/parametername/test
/// Tainted source: query param KEY name
async fn iast_source_parametername_get(request: Request) -> Response {
    let raw_query = request.uri().query().unwrap_or("").to_owned();
    let key = url::form_urlencoded::parse(raw_query.as_bytes())
        .find(|(k, _)| k == "table")
        .map(|(k, _)| k.into_owned())
        .unwrap_or_default();
    let _ = md5::compute(key.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /iast/source/parametername/test
/// Tainted source: form-urlencoded body param KEY name
async fn iast_source_parametername_post(body: Bytes) -> Response {
    let key = url::form_urlencoded::parse(&body)
        .find(|(k, _)| k == "user")
        .map(|(k, _)| k.into_owned())
        .unwrap_or_default();
    let _ = md5::compute(key.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// GET /iast/source/header/test
/// Tainted source: request header value
async fn iast_source_header(headers: HeaderMap) -> Response {
    let val = headers
        .get("table")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_owned();
    let _ = md5::compute(val.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// GET /iast/source/headername/test
/// Tainted source: request header NAME
async fn iast_source_headername(headers: HeaderMap) -> Response {
    let mut name_str = String::new();
    for (name, _) in &headers {
        if name.as_str() == "table" {
            name_str = name.as_str().to_owned();
            break;
        }
    }
    let _ = md5::compute(name_str.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// GET /iast/source/cookievalue/test
/// Tainted source: cookie VALUE for key "table"
async fn iast_source_cookievalue(headers: HeaderMap) -> Response {
    let val = headers
        .get("cookie")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .split(';')
        .filter_map(|part| {
            let part = part.trim();
            let eq = part.find('=')?;
            let k = part[..eq].trim();
            let v = part[eq + 1..].trim();
            if k == "table" { Some(v.to_owned()) } else { None }
        })
        .next()
        .unwrap_or_default();
    let _ = md5::compute(val.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// GET /iast/source/cookiename/test
/// Tainted source: cookie KEY name "table"
async fn iast_source_cookiename(headers: HeaderMap) -> Response {
    let key = headers
        .get("cookie")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .split(';')
        .filter_map(|part| {
            let part = part.trim();
            let eq = part.find('=')?;
            let k = part[..eq].trim();
            if k == "table" { Some(k.to_owned()) } else { None }
        })
        .next()
        .unwrap_or_default();
    let _ = md5::compute(key.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /iast/source/multipart/test
/// Tainted source: uploaded file name from multipart
async fn iast_source_multipart(mut multipart: axum::extract::Multipart) -> Response {
    let mut filename = String::new();
    while let Ok(Some(field)) = multipart.next_field().await {
        if let Some(f) = field.file_name() {
            filename = f.to_owned();
            break;
        }
    }
    let _ = md5::compute(filename.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /iast/source/body/test
/// Tainted source: JSON body field "name"
async fn iast_source_body(Json(body): Json<Value>) -> Response {
    let name_val = body
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_owned();
    let _ = md5::compute(name_val.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// GET /iast/source/sql/test
/// Tainted source: DB query result used in second query (SQL injection taint flow)
async fn iast_source_sql() -> Response {
    use rusqlite::Connection;
    let conn = match Connection::open_in_memory() {
        Ok(c) => c,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, "db error").into_response(),
    };
    let _ = conn.execute_batch(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
         INSERT INTO users (id, name) VALUES (1, 'system_tests_user');",
    );
    let username: String = conn
        .query_row("SELECT name FROM users WHERE id=1", [], |row| row.get(0))
        .unwrap_or_else(|_| "unknown".to_owned());
    // Vulnerable: tainted DB value concatenated into second query
    let vuln_query = format!("SELECT * FROM users WHERE name='{username}'");
    let _ = conn.execute_batch(&vuln_query);
    (StatusCode::OK, "OK").into_response()
}

// ─── IAST SC (security controls) ─────────────────────────────────────────────

#[derive(Deserialize)]
struct IastScBody {
    param: Option<String>,
}

/// POST /iast/sc/s/configured
async fn iast_sc_s_configured(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/s/not-configured
async fn iast_sc_s_not_configured(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/s/all
async fn iast_sc_s_all(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/iv/configured
async fn iast_sc_iv_configured(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/iv/not-configured
async fn iast_sc_iv_not_configured(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/iv/all
async fn iast_sc_iv_all(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/iv/overloaded/secure
async fn iast_sc_iv_overloaded_secure(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/iv/overloaded/insecure
async fn iast_sc_iv_overloaded_insecure(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/s/overloaded/secure
async fn iast_sc_s_overloaded_secure(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}

/// POST /sc/s/overloaded/insecure
async fn iast_sc_s_overloaded_insecure(Json(body): Json<IastScBody>) -> Response {
    let param = body.param.unwrap_or_default();
    let _ = md5::compute(param.as_bytes());
    (StatusCode::OK, "OK").into_response()
}
