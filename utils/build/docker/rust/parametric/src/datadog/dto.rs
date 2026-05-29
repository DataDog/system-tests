use datadog_opentelemetry::configuration::Config;
use datadog_opentelemetry::log::LevelFilter;
use serde::{ser::SerializeSeq, Deserialize, Deserializer, Serialize, Serializer};
use std::collections::HashMap;

// --- KeyValue ---
#[derive(Debug, Clone)]
pub struct KeyValue {
    pub key: String,
    pub value: String,
}

// --- SpanErrorArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanErrorArgs {
    pub span_id: u64,
    pub r#type: String,
    pub message: String,
    pub stack: String,
}

// --- SpanExtractHeadersArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanExtractHeadersArgs {
    #[serde(
        serialize_with = "key_value_vec::serialize",
        deserialize_with = "key_value_vec::deserialize"
    )]
    pub http_headers: Vec<KeyValue>,
}

// --- SpanExtractHeadersResult ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanExtractHeadersResult {
    pub span_id: Option<u64>,
}

// --- SpanFinishArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanFinishArgs {
    pub span_id: u64,
}

// --- SpanGetAllBaggageArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanGetAllBaggageArgs {
    pub span_id: u64,
}

// --- SpanGetAllBaggageResult ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanGetAllBaggageResult {
    pub baggage: Option<HashMap<String, String>>,
}

// --- SpanGetBaggageArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanGetBaggageArgs {
    pub span_id: u64,
    pub key: String,
}

// --- SpanGetBaggageResult ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanGetBaggageResult {
    pub baggage: Option<String>,
}

// --- SpanInjectHeadersArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanInjectHeadersArgs {
    pub span_id: u64,
}

// --- SpanInjectHeadersResult ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanInjectHeadersResult {
    pub http_headers: Vec<KeyValue>,
}

// --- SpanRemoveAllBaggageArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanRemoveAllBaggageArgs {
    pub span_id: u64,
}

// --- SpanRemoveBaggageArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanRemoveBaggageArgs {
    pub span_id: u64,
    pub key: String,
}

// --- SpanSetBaggageArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanSetBaggageArgs {
    pub span_id: u64,
    pub key: String,
    pub value: String,
}

// --- SpanSetMetaArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanSetMetaArgs {
    pub span_id: u64,
    pub key: String,
    pub value: String,
}

// --- SpanSetMetricArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanSetMetricArgs {
    pub span_id: u64,
    pub key: String,
    pub value: f64,
}

// --- ManualSamplingArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ManualSamplingArgs {
    pub span_id: u64,
}

// --- SpanSetResourceArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SpanSetResourceArgs {
    pub span_id: u64,
    pub resource: String,
}

// --- StartSpanArgs ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct StartSpanArgs {
    pub parent_id: Option<u64>,
    pub name: String,
    pub service: Option<String>,
    pub r#type: Option<String>,
    pub resource: Option<String>,

    #[serde(
        serialize_with = "key_value_vec::serialize",
        deserialize_with = "key_value_vec::deserialize"
    )]
    pub span_tags: Vec<KeyValue>,
}

// --- StartSpanResult ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct StartSpanResult {
    pub span_id: u64,
    pub trace_id: u128,
}

impl StartSpanResult {
    pub fn error() -> Self {
        StartSpanResult {
            span_id: 0,
            trace_id: 0,
        }
    }
}

// --- FlushResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct FlushResult {
    pub success: bool,
}

/// Body for `GET /trace/config` — matches Python `TraceConfigReturn` (`config` key).
#[derive(Debug, Serialize)]
pub struct TraceConfigResponse {
    pub config: ConfigResult,
}

#[derive(Debug, Serialize)]
pub struct ConfigResult {
    pub dd_service: Option<String>,
    pub dd_log_level: Option<String>,
    pub dd_trace_sample_rate: Option<String>,
    pub dd_trace_enabled: Option<String>,
    pub dd_runtime_metrics_enabled: Option<String>,
    pub dd_tags: Option<String>,
    pub dd_trace_propagation_style: Option<String>,
    pub dd_trace_debug: Option<String>,
    pub dd_trace_otel_enabled: Option<String>,
    pub dd_trace_sample_ignore_parent: Option<String>,
    pub dd_env: Option<String>,
    pub dd_version: Option<String>,
    pub dd_trace_agent_url: Option<String>,
    pub dd_trace_rate_limit: Option<String>,
    pub dd_dogstatsd_host: Option<String>,
    pub dd_dogstatsd_port: Option<String>,
    pub dd_logs_injection: Option<String>,
    pub dd_profiling_enabled: Option<String>,
    pub dd_data_streams_enabled: Option<String>,
}

fn format_global_tags(config: &Config) -> String {
    config
        .global_tags()
        .map(|(k, v)| format!("{k}:{v}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn format_trace_propagation_extract(config: &Config) -> String {
    config
        .trace_propagation_style_extract()
        .map(|styles| {
            styles
                .iter()
                .map(std::string::ToString::to_string)
                .collect::<Vec<_>>()
                .join(",")
        })
        .unwrap_or_default()
}

fn bool_str(on: bool) -> String {
    if on {
        "true".to_string()
    } else {
        "false".to_string()
    }
}

impl From<Config> for ConfigResult {
    fn from(config: Config) -> Self {
        let dd_trace_debug = matches!(*config.log_level_filter(), LevelFilter::Debug);

        Self {
            dd_service: Some(config.service().to_string()),
            dd_log_level: Some(config.log_level_filter().to_string().to_lowercase()),
            dd_trace_sample_rate: None,
            dd_trace_enabled: Some(bool_str(config.enabled())),
            dd_runtime_metrics_enabled: Some(bool_str(config.metrics_otel_enabled())),
            dd_tags: Some(format_global_tags(&config)),
            dd_trace_propagation_style: Some(format_trace_propagation_extract(&config)),
            dd_trace_debug: Some(bool_str(dd_trace_debug)),
            dd_trace_otel_enabled: None,
            dd_trace_sample_ignore_parent: None,
            dd_env: config.env().map(str::to_string),
            dd_version: config.version().map(str::to_string),
            dd_trace_agent_url: Some(config.trace_agent_url().to_string()),
            dd_trace_rate_limit: Some(config.trace_rate_limit().to_string()),
            dd_dogstatsd_host: Some(config.dogstatsd_agent_host().to_string()),
            dd_dogstatsd_port: Some(config.dogstatsd_agent_port().to_string()),
            dd_logs_injection: None,
            dd_profiling_enabled: None,
            dd_data_streams_enabled: None,
        }
    }
}

// Custom serialization: as [["key", "value"], ...]
impl Serialize for KeyValue {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut seq = serializer.serialize_seq(Some(2))?;
        seq.serialize_element(&self.key)?;
        seq.serialize_element(&self.value)?;
        seq.end()
    }
}

// Custom deserialization: from ["key", "value"]
impl<'de> Deserialize<'de> for KeyValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let arr: Vec<String> = Vec::deserialize(deserializer)?;
        if arr.len() != 2 {
            return Err(serde::de::Error::custom("Expected array of length 2"));
        }
        Ok(KeyValue {
            key: arr[0].clone(),
            value: arr[1].clone(),
        })
    }
}

/// Serde helpers for Vec<KeyValue> as array of arrays
pub mod key_value_vec {
    use super::KeyValue;
    use serde::ser::SerializeSeq;
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(items: &Vec<KeyValue>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut seq = serializer.serialize_seq(Some(items.len()))?;
        for kv in items {
            seq.serialize_element(&kv)?;
        }
        seq.end()
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Vec<KeyValue>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let arrs: Vec<Vec<String>> = Vec::deserialize(deserializer)?;
        arrs.into_iter()
            .map(|arr| {
                if arr.len() != 2 {
                    Err(serde::de::Error::custom("Expected array of length 2"))
                } else {
                    Ok(KeyValue {
                        key: arr[0].clone(),
                        value: arr[1].clone(),
                    })
                }
            })
            .collect()
    }
}
