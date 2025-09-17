use ::opentelemetry::global::{self, BoxedTracer};
use anyhow::{Context, Result};
use axum::{
    body::Body, error_handling::HandleErrorLayer, extract::Request, http::StatusCode, BoxError,
    Router,
};
use hyper::body::Incoming;
use hyper_util::rt::TokioIo;
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
use tower::{Service, ServiceBuilder};
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
    contexts: Arc<Mutex<HashMap<u64, Arc<ContextWithParent>>>>,
    current_context: Arc<Mutex<Arc<ContextWithParent>>>,
    extracted_span_contexts: Arc<Mutex<HashMap<u64, ::opentelemetry::Context>>>,
    tracer_provider: SdkTracerProvider,
}

#[derive(Default, Clone)]
struct ContextWithParent {
    context: ::opentelemetry::Context,
    parent: Option<::opentelemetry::Context>,
}

impl ContextWithParent {
    fn new(context: ::opentelemetry::Context, parent: Option<::opentelemetry::Context>) -> Self {
        ContextWithParent { context, parent }
    }
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
    if let Err(ref error) = run(tracer).await {
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
    Ok(datadog_opentelemetry::tracing()
        .with_config(builder.build())
        .init())
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

pub async fn serve(config: Config, tracer_provider: SdkTracerProvider) -> Result<()> {
    let Config {
        addr,
        port,
        shutdown_timeout,
    } = config;

    let current_context = Arc::new(Mutex::new(Arc::new(ContextWithParent::default())));

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

    serve_plain(listener, app, shutdown_timeout).await
}

/// It seems axum server returns a "connection": "keep-alive" header by default causing the tests fail randomly with a
/// requests.exceptions.ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
///
/// Some tests end with making POST request to /trace/span/flush, /trace/stats/flush and /trace/otel/flush
/// and seems that the keep-alive is not handled correctly by the python client:
/// https://github.com/python/cpython/issues/85517
///
/// This funtion is just to set keep_alive = false (because axum doesn't allow to configure it)
/// and it is inspired by this example https://github.com/tokio-rs/axum/blob/v0.7.x/examples/serve-with-hyper/src/main.rs
async fn serve_plain(
    listener: TcpListener,
    app: Router,
    _shutdown_timeout: Option<Duration>,
) -> Result<()> {
    loop {
        let (socket, _remote_addr) = listener.accept().await.unwrap();

        let tower_service = app.clone();

        tokio::spawn(async move {
            let socket = TokioIo::new(socket);
            let hyper_service = hyper::service::service_fn(move |request: Request<Incoming>| {
                tower_service.clone().call(request)
            });

            let mut server = hyper::server::conn::http1::Builder::new();
            server.keep_alive(false);

            if let Err(err) = server.serve_connection(socket, hyper_service).await {
                error!("failed to serve connection: {err:#}");
            }
        });
    }
}

async fn serve_axum(
    listener: TcpListener,
    app: Router,
    shutdown_timeout: Option<Duration>,
) -> Result<()> {
    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(shutdown_signal(shutdown_timeout))
        .await
        .context("run server")
}

async fn shutdown_signal(shutdown_timeout: Option<Duration>) {
    let res = signal(SignalKind::terminate())
        .expect("install SIGTERM handler")
        .recv()
        .await;
    debug!("Shutdown signal received, preparing to close server. {res:?}");

    if let Some(shutdown_timeout) = shutdown_timeout {
        sleep(shutdown_timeout).await;
        debug!("Shutdown signal received, closing!!");
    }
}

fn make_span(request: &Request<Body>) -> Span {
    let headers = request.headers();
    let path = request.uri().path();

    println!("creating span for {path}");

    info_span!("incoming request", path, ?headers, trace_id = field::Empty)
}

async fn run(tracer: SdkTracerProvider) -> Result<()> {
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
