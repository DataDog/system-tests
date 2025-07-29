use ::opentelemetry::global::{self, BoxedTracer};
use anyhow::{Context, Result};
use axum::{
    body::Body, error_handling::HandleErrorLayer, extract::Request, http::StatusCode, routing::get,
    BoxError, Router,
};
use opentelemetry_sdk::trace::SdkTracerProvider;
use serde::Deserialize;
use serde_json::json;
use std::{
    collections::HashMap,
    env,
    fmt::Display,
    net::{IpAddr, Ipv4Addr},
    panic,
    sync::{Arc, Mutex, OnceLock},
    time::Duration,
};
use time::{format_description::well_known::Rfc3339, OffsetDateTime};
use tokio::{
    net::TcpListener,
    signal::unix::{signal, SignalKind},
    time::sleep,
};
use tower::ServiceBuilder;
use tower_http::trace::{DefaultOnFailure, DefaultOnRequest, DefaultOnResponse, TraceLayer};
use tracing::{debug, error, field, info, info_span, Level, Span};
use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

mod datadog;
mod opentelemetry;

pub(crate) fn get_tracer() -> &'static BoxedTracer {
    static TRACER: OnceLock<BoxedTracer> = OnceLock::new();
    TRACER.get_or_init(|| global::tracer("ddtrace-rust-client"))
}

#[derive(Clone)]
struct AppState {
    contexts: Arc<Mutex<HashMap<u64, ::opentelemetry::Context>>>,
    extracted_span_contexts: Arc<Mutex<HashMap<u64, ::opentelemetry::Context>>>,
    tracer_provider: Arc<SdkTracerProvider>,
    current_context: Arc<Mutex<::opentelemetry::Context>>,
}

#[tokio::main]
async fn main() {
    // If tracing initialization fails, nevertheless emit a structured log event.
    let result = init_tracing();
    let tracer = match result {
        Ok(tracer) => tracer,
        Err(ref error) => {
            log_error(error);
            return;
        }
    };

    // Replace the default panic hook with one that uses structured logging at ERROR level.
    panic::set_hook(Box::new(|panic| error!(%panic, "process panicked")));

    // Run and log any error.
    if let Err(ref error) = run(Arc::new(tracer)).await {
        error!(
            error = format!("{error:#}"),
            backtrace = %error.backtrace(),
            "process exited with ERROR"
        );
    }
}

fn init_tracing() -> Result<SdkTracerProvider> {
    let _ = tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| {
            format!(
                "{}=debug", // ,hyper=debug,tower_http=debug
                env!("CARGO_CRATE_NAME")
            )
            .into()
        }))
        .with(fmt::layer().json().flatten_event(true))
        .try_init()
        .context("initialize tracing subscriber");

    let mut builder = dd_trace::Config::builder();
    builder.set_log_level_filter(dd_trace::log::LevelFilter::Debug);
    Ok(datadog_opentelemetry::init_datadog(
        builder.build(),
        SdkTracerProvider::builder(),
        None,
    ))
}

fn log_error(error: &impl Display) {
    let now = OffsetDateTime::now_utc().format(&Rfc3339).unwrap();
    let error = serde_json::to_string(&json!({
        "timestamp": now,
        "level": "ERROR",
        "message": "process exited with ERROR",
        "error": format!("{error:#}")
    }));

    // Not using `eprintln!`, because `tracing_subscriber::fmt` uses stdout by default.
    println!("{}", error.unwrap());
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub struct Config {
    addr: IpAddr,
    port: u16,
    #[serde(with = "humantime_serde")]
    shutdown_timeout: Option<Duration>,
}

pub async fn serve(config: Config, tracer_provider: Arc<SdkTracerProvider>) -> Result<()> {
    let Config {
        addr,
        port,
        shutdown_timeout,
    } = config;

    let current_context = Arc::new(Mutex::new(::opentelemetry::Context::current()));

    let state = AppState {
        contexts: Arc::new(Mutex::new(HashMap::new())),
        extracted_span_contexts: Arc::new(Mutex::new(HashMap::new())),
        tracer_provider,
        current_context,
    };

    let app = Router::new()
        .nest("/trace", datadog::app())
        .nest("/trace/otel", opentelemetry::app())
        .layer(
            ServiceBuilder::new()
                .layer(HandleErrorLayer::new(|err: BoxError| async move {
                    error!("HandleErrorLayer: {}", &err);
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("Unhandled error: {err}"),
                    )
                }))
                .layer(
                    TraceLayer::new_for_http()
                        .make_span_with(make_span)
                        .on_request(DefaultOnRequest::new().level(Level::DEBUG))
                        .on_response(DefaultOnResponse::new().level(Level::DEBUG))
                        .on_failure(DefaultOnFailure::new().level(Level::ERROR)),
                )
                .timeout(Duration::from_secs(30)),
        )
        .with_state(state);

    let listener = TcpListener::bind((addr, port))
        .await
        .context("bind TcpListener")?;

    info!("Axus Server listening on port {port}");

    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(shutdown_signal(shutdown_timeout))
        .await
        .context("run server")
}

async fn shutdown_signal(shutdown_timeout: Option<Duration>) {
    signal(SignalKind::terminate())
        .expect("install SIGTERM handler")
        .recv()
        .await;
    debug!("Shutdown signal received, preparing to close server.");
    if let Some(shutdown_timeout) = shutdown_timeout {
        sleep(shutdown_timeout).await;
        debug!("Shutdown signal received, closing!!");
    }
}

fn make_span(request: &Request<Body>) -> Span {
    let headers = request.headers();
    let path = request.uri().path();

    debug!("creating span for {path}");

    info_span!("incoming request", path, ?headers, trace_id = field::Empty)
}

async fn run(tracer: Arc<SdkTracerProvider>) -> Result<()> {
    let port = u16::from_str_radix(
        &env::var("APM_TEST_CLIENT_SERVER_PORT").unwrap_or("8080".to_string()),
        10,
    )?;

    let config = Config {
        addr: IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)),
        port,
        shutdown_timeout: Some(Duration::new(3, 0)),
    };

    info!(?config, "starting");

    serve(config, tracer).await
}
