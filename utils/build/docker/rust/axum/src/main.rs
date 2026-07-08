use std::collections::HashMap;

use axum::{
    extract::Query,
    http::StatusCode,
    middleware::{self},
    response::{IntoResponse, Response},
    routing::{get, options, post},
    Json, Router,
};

use opentelemetry::trace::TracerProvider;
use reqwest_middleware::ClientBuilder;
use reqwest_tracing::TracingMiddleware;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use integration::DatadogClientSpanBackend;

mod integration;

const VERSION_FILE: &str = "/app/SYSTEM_TESTS_LIBRARY_VERSION";

#[tokio::main]
async fn main() {
    let tracer_provider = datadog_opentelemetry::tracing().init();
    tracing_subscriber::registry()
        .with(tracing_opentelemetry::layer().with_tracer(tracer_provider.tracer("weblog")))
        .init();

    let app = Router::new()
        .route("/", get(index))
        .route("/", post(index))
        .route("/", options(index))
        // Basic info endpoints
        .route("/healthcheck", get(healthcheck))
        .route("/make_distant_call", get(make_distant_call))
        .layer(middleware::from_fn(integration::enrich_span))
        .layer(opentelemetry_instrumentation_tower::HTTPLayer::default())
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

    // `TracingMiddleware` creates a client span nested under the current
    // (server) tracing span and injects its OTel context into the outgoing
    // request headers automatically.
    let client = ClientBuilder::new(reqwest::Client::new())
        .with(TracingMiddleware::<DatadogClientSpanBackend>::new())
        .build();

    let resp = client.get(&url).send().await;

    match resp {
        Ok(r) => {
            let status = r.status().as_u16();
            Json(serde_json::json!({
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
