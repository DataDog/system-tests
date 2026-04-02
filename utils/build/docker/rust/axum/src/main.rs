use std::{collections::HashMap, str::FromStr as _};

use axum::{
    extract::{MatchedPath, Query},
    http::{Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    routing::{get, options, post},
    Json, Router,
};
use opentelemetry::trace::TracerProvider as _;
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
        .route("/", get(index))
        .route("/", post(index))
        .route("/", options(index))
        .route("/healthcheck", get(healthcheck))
        .route("/stats-unique", get(stats_unique))
        .route("/rasp/sqli", get(rasp_sqli))
        .route("/make_distant_call", get(make_distant_call))
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
    tracing::Span::current().set_attribute("http.route", matched_path.as_str().to_owned());
    next.run(req).await
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

// Simulates a SQL query span for client-side stats obfuscation testing.
// datadog-opentelemetry does not obfuscate SQL server-side, so we emit the
// already-obfuscated statement directly. The span kind "client" + db.system
// "sqlite" → type "sql", and "client" is in span_kinds_stats_computed so
// TopLevelHits == Hits.
async fn rasp_sqli(Query(_params): Query<HashMap<String, String>>) -> Response {
    // parent: None makes this a trace root so that _top_level=1 → TopLevelHits=Hits.
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

// Proxies a GET request to the given URL and returns basic response info.
// The outbound HTTP span has server.address set, which is in the agent's
// peer_tags list → SpanConcentrator includes it in PeerTags for stats.
async fn make_distant_call(Query(params): Query<HashMap<String, String>>) -> Response {
    let url = params.get("url").cloned().unwrap_or_default();
    let host = reqwest::Url::parse(&url)
        .ok()
        .and_then(|u| u.host_str().map(str::to_owned))
        .unwrap_or_default();

    // server.address is mapped to http.server_name in the Datadog attribute schema,
    // which isn't in the test's expected peer tag prefixes. Also set out.host
    // which passes through as-is and matches the "out.host" prefix.
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
            Json(json!({ "url": url, "status_code": r.status().as_u16() })).into_response()
        }
        Err(e) => {
            tracing::warn!("make_distant_call failed: {e}");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}
