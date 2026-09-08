//! Axum server-side span enrichment.

use axum::{
    extract::{MatchedPath, Request},
    middleware::{self, Next},
    response::Response,
    Router,
};
use opentelemetry::{
    global,
    trace::{FutureExt, SpanKind, Status, TraceContextExt, Tracer},
    KeyValue,
};
use opentelemetry_http::HeaderExtractor;

use super::dd_tags;

/// Installs the single middleware that creates the inbound HTTP server span and
/// enriches it with the Datadog attributes `validate_all_spans` expects.
pub fn install_middleware(router: Router) -> Router {
    router.layer(middleware::from_fn(datadog_specific_axum_layer))
}

/// Creates the inbound server span on the OpenTelemetry `Context` (extracting any
/// upstream trace context from the request headers), makes it current for the
/// downstream handler, and records both the OTel HTTP semantic-convention
/// attributes and the Datadog-specific attributes needed by `validate_all_spans`.
async fn datadog_specific_axum_layer(request: Request, next: Next) -> Response {
    // Extract any upstream trace context propagated in the inbound headers.
    let parent_cx = global::get_text_map_propagator(|propagator| {
        propagator.extract(&HeaderExtractor(request.headers()))
    });

    // Low-cardinality route from axum's matched path (e.g. "/params/{value}"),
    // falling back to a method-only span name when no route matched.
    let method = request.method().as_str().to_owned();
    let route = request
        .extensions()
        .get::<MatchedPath>()
        .map(|p| p.as_str().to_owned());
    let span_name = route
        .as_ref()
        .map_or_else(|| method.clone(), |r| format!("{method} {r}"));

    // server.address and http.url are built from the request URI + Host header.
    let host = request
        .headers()
        .get(axum::http::header::HOST)
        .and_then(|h| h.to_str().ok())
        .unwrap_or("localhost:7777")
        .to_owned();
    let server_address = host.split(':').next().unwrap_or(&host).to_owned();
    let path = request.uri().path().to_owned();
    // Query-string obfuscation is a tracer responsibility, so report verbatim.
    let query_suffix = request
        .uri()
        .query()
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let url = format!("http://{host}{path}{query_suffix}");

    // OTel HTTP server-span attributes (semantic conventions) ...
    let mut attributes = vec![
        KeyValue::new("http.request.method", method.clone()),
        KeyValue::new("url.path", path),
        KeyValue::new("url.full", request.uri().to_string()),
    ];
    if let Some(user_agent) = request
        .headers()
        .get(axum::http::header::USER_AGENT)
        .and_then(|v| v.to_str().ok())
    {
        attributes.push(KeyValue::new("user_agent.original", user_agent.to_owned()));
    }
    if let Some(route) = &route {
        attributes.push(KeyValue::new("http.route", route.clone()));
    }
    // ... plus the Datadog-specific attributes.
    attributes.extend(dd_tags());
    attributes.push(KeyValue::new("http.url", url));
    attributes.push(KeyValue::new("server.address", server_address));
    // _dd.top_level marks this as a root span so the library interface can match
    // traces to requests via the user-agent header.
    attributes.push(KeyValue::new("_dd.top_level", 1i64));

    let tracer = global::tracer("weblog");
    let span = tracer
        .span_builder(span_name)
        .with_kind(SpanKind::Server)
        .with_attributes(attributes)
        .start_with_context(&tracer, &parent_cx);
    let cx = parent_cx.with_span(span);

    // Run the downstream handler with the server span as the current context.
    let response = next.run(request).with_context(cx.clone()).await;

    // Record the response status on the span before it ends (on drop of `cx`).
    let span = cx.span();
    let status = response.status().as_u16();
    span.set_attribute(KeyValue::new("http.response.status_code", i64::from(status)));
    if status >= 500 {
        span.set_status(Status::Error {
            description: format!("HTTP {status}").into(),
        });
    }

    response
}
