use std::collections::HashMap;

use axum::{
    extract::{Query, Request},
    http::StatusCode,
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use opentelemetry::{
    context::FutureExt,
    global,
    trace::{TraceContextExt, Tracer},
    Context,
};
use opentelemetry_http::{HeaderExtractor, HeaderInjector};

const VERSION_FILE: &str = "/app/SYSTEM_TESTS_LIBRARY_VERSION";


async fn trace_request(request: Request, next: Next) -> Response {
    let parent_cx = global::get_text_map_propagator(|propagator| {
        propagator.extract(&HeaderExtractor(request.headers()))
    });

    let tracer = global::tracer("rust-axum-weblog");
    let span = tracer.start_with_context(request.uri().path().to_string(), &parent_cx);

    // Run the rest of the request with the span's context set as current so
    // downstream handlers (e.g. make_distant_call) can inject it into
    // outgoing requests. The span ends when `cx`, and the span it owns, are
    // dropped.
    let cx = parent_cx.with_span(span);
    next.run(request).with_context(cx).await
}

#[tokio::main]
async fn main() {
    let tracer_provider = datadog_opentelemetry::tracing().init();

    let app = Router::new()
        // Root endpoint
        .route("/", get(index))
        .route("/", post(index))
        // Basic info endpoints
        .route("/healthcheck", get(healthcheck))
        .route("/make_distant_call", get(make_distant_call))
        .layer(middleware::from_fn(trace_request))
        .into_make_service();

    let listener = tokio::net::TcpListener::bind("0.0.0.0:7777").await.unwrap();
    println!("Listening on port 7777");
    axum::serve(listener, app).await.unwrap();

    tracer_provider.shutdown().unwrap();
}

// ─── Basic endpoints ─────────────────────────────────────────────────────────

async fn healthcheck() -> Json<serde_json::Value> {
    let version = std::fs::read_to_string(VERSION_FILE).unwrap_or_else(|_| "unknown".to_string());
    let version = version.trim().to_string();
    Json(serde_json::json!({
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

// ─── External request endpoints ─────────────────────────────────────────────

async fn make_distant_call(Query(params): Query<HashMap<String, String>>) -> Response {
    let url = params.get("url").cloned().unwrap_or_default();
    tracing::Span::current().record("url", &url);

    let mut headers = axum::http::HeaderMap::new();
    global::get_text_map_propagator(|propagator| {
        propagator.inject_context(&Context::current(), &mut HeaderInjector(&mut headers))
    });

    let request_headers: HashMap<String, String> = headers
        .iter()
        .map(|(name, value)| {
            (
                name.to_string(),
                value.to_str().unwrap_or_default().to_string(),
            )
        })
        .collect();

    let resp = reqwest::Client::new()
        .get(&url)
        .headers(headers)
        .send()
        .await;

    match resp {
        Ok(r) => {
            let status = r.status().as_u16();
            Json(serde_json::json!({
                "url": url,
                "status_code": status,
                "request_headers": request_headers,
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
