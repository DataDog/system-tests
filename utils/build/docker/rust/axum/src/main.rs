use std::{collections::HashMap, str::FromStr as _};

use axum::{
    extract::Query,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, options, post},
    Json, Router,
};
use opentelemetry::trace::TracerProvider as _;
use serde_json::{json, Value};
use tower_otel::{metrics, trace};
use tracing::{level_filters::LevelFilter, Level};
use tracing_subscriber::{
    fmt::format::FmtSpan, layer::SubscriberExt as _, util::SubscriberInitExt, Layer as _,
};

const VERSION_FILE: &str = "/app/SYSTEM_TESTS_LIBRARY_VERSION";

#[tokio::main]
async fn main() {
    let tracer_provider = datadog_opentelemetry::tracing().init();
    let meter_provider = datadog_opentelemetry::metrics().init();

    const PKG_NAME: &str = env!("CARGO_PKG_NAME");
    // const PKG_VERSION: &str = env!("CARGO_PKG_VERSION");

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
        .layer(trace::HttpLayer::server(Level::DEBUG))
        .layer(metrics::HttpLayer::server(&meter))
        .route("/", get(index))
        .route("/", post(index))
        .route("/", options(index))
        .route("/healthcheck", get(healthcheck))
        .route("/stats-unique", get(stats_unique))
        .into_make_service();
    let listener = tokio::net::TcpListener::bind("0.0.0.0:7777").await.unwrap();
    println!("Listening on port 7777");
    axum::serve(listener, app).await.unwrap();

    meter_provider.shutdown().unwrap();
    tracer_provider.shutdown().unwrap();
}

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

async fn index() -> &'static str {
    "Hello, World!"
}

async fn stats_unique(Query(query_params): Query<HashMap<String, String>>) -> Response {
    let code = query_params
        .get("code")
        .and_then(|code| StatusCode::from_str(code).ok())
        .unwrap_or(StatusCode::OK);
    if code == StatusCode::NO_CONTENT {
        StatusCode::NO_CONTENT.into_response()
    } else {
        (code, "OK, probably").into_response()
    }
}
