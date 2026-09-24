//! Tracing and span-enrichment utilities for Datadog compatibility.
//!
//! This module adds Datadog-specific semantic-convention attributes to both
//! inbound (server) and outgoing (client) HTTP spans so they satisfy the
//! system-tests' `validate_all_spans` checks.
//!
//! Future work: If a proper datadog integration for axum gets implemented,
//! refactor to use it instead

mod axum_layer;
mod reqwest_backend;

pub use axum_layer::install_middleware;
pub use reqwest_backend::{
    header_map_to_string_map, CaptureRequestHeaders, DatadogClientSpanBackend,
};

use opentelemetry::{trace::TracerProvider, KeyValue};
use opentelemetry_sdk::trace::SdkTracerProvider;
use std::sync::OnceLock;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

/// Initializes the Datadog tracer provider and installs it as the global
/// `tracing` subscriber, so `tracing::info_span!` etc. produce Datadog-backed spans.
pub fn install_datadog_tracing() -> SdkTracerProvider {
    let tracer_provider = datadog_opentelemetry::tracing().init();
    tracing_subscriber::registry()
        .with(tracing_opentelemetry::layer().with_tracer(tracer_provider.tracer("weblog")))
        .init();
    tracer_provider
}

/// Helper returning datadog semantic-convention tags every span needs to satisfy
/// Used in both reqwest and axum middleware
/// (necessary for test `validate_all_spans`)
fn dd_tags() -> Vec<KeyValue> {
    /// Single runtime-id for the lifetime of this process.
    static RUNTIME_ID: OnceLock<String> = OnceLock::new();

    vec![
        KeyValue::new("language", "rust"),
        KeyValue::new("component", "axum"),
        KeyValue::new(
            "runtime-id",
            RUNTIME_ID
                .get_or_init(|| uuid::Uuid::new_v4().to_string())
                .as_str(),
        ),
        // process_id goes to the metrics map (numeric value).
        KeyValue::new("process_id", std::process::id() as i64),
    ]
}
