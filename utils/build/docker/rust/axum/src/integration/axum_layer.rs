//! Axum server-side span enrichment.

use axum::{
    extract::Request,
    middleware::{self, Next},
    response::Response,
    Router,
};
use opentelemetry::{trace::TraceContextExt, Context, KeyValue};

use super::dd_tags;

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
