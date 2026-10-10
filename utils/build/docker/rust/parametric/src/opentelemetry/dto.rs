use std::{
    collections::HashMap,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use opentelemetry::trace::{SpanKind, Status};
use opentelemetry::KeyValue;
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

// --- AddEventArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct AddEventArgs {
    pub span_id: u64,
    pub name: String,
    pub timestamp: Option<i64>,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

// --- EndSpanArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct EndSpanArgs {
    pub id: u64,
    pub timestamp: Option<i64>,
}

// --- FlushArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct FlushArgs {
    pub seconds: i64,
}

// --- FlushResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct FlushResult {
    pub success: bool,
}

// --- GetAllBaggageResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct GetAllBaggageResult {
    pub baggage: Option<HashMap<String, String>>,
}

// --- GetBaggageArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct GetBaggageArgs {
    pub key: String,
}

// --- GetBaggageResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct GetBaggageResult {
    pub value: Option<String>,
}

// --- IsRecordingArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct IsRecordingArgs {
    pub span_id: u64,
}

// --- IsRecordingResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct IsRecordingResult {
    pub is_recording: bool,
}

// --- RecordExceptionArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct RecordExceptionArgs {
    pub span_id: u64,
    pub message: String,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

// --- RemoveBaggageArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct RemoveBaggageArgs {
    pub key: String,
}

// --- SetAttributesArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SetAttributesArgs {
    pub span_id: u64,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

// --- SetBaggageArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SetBaggageArgs {
    pub span_id: u64,
    pub key: String,
    pub value: String,
}

// --- SetNameArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SetNameArgs {
    pub span_id: u64,
    pub name: String,
}

// --- SetStatusArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SetStatusArgs {
    pub span_id: u64,
    pub code: String,
    pub description: String,
}

// --- SpanContextArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SpanContextArgs {
    pub span_id: u64,
}

// --- SpanContextResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SpanContextResult {
    pub span_id: u64,
    pub trace_id: String,
    pub trace_flags: Option<String>,
    pub trace_state: Option<String>,
    pub remote: Option<bool>,
}

// --- SpanLink ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SpanLink {
    #[serde(rename = "parent_id")]
    pub parent_id: u64,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

// --- StartSpanArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct StartSpanArgs {
    pub parent_id: Option<u64>,
    pub name: String,
    pub span_kind: Option<i32>,
    pub timestamp: Option<i64>,
    pub links: Option<Vec<SpanLink>>,
    #[serde(default)]
    pub events: Vec<StartSpanEvent>,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

// --- StartSpanEvent ---
#[derive(Debug, Serialize, Deserialize)]
pub struct StartSpanEvent {
    pub time_unix_nano: u64,
    pub name: String,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

// --- StartSpanResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct StartSpanResult {
    pub span_id: u64,
    pub trace_id: u64,
}

impl StartSpanResult {
    pub fn error() -> Self {
        StartSpanResult {
            span_id: 0,
            trace_id: 0,
        }
    }
}

pub fn system_time_from_micros(micros: i64) -> SystemTime {
    if micros >= 0 {
        UNIX_EPOCH + Duration::from_micros(micros as u64)
    } else {
        UNIX_EPOCH - Duration::from_micros((-micros) as u64)
    }
}

pub fn parse_span_kind(span_kind: i32) -> Option<SpanKind> {
    match span_kind {
        0 => Some(SpanKind::Internal),
        1 => Some(SpanKind::Server),
        2 => Some(SpanKind::Client),
        3 => Some(SpanKind::Producer),
        4 => Some(SpanKind::Consumer),
        _ => None,
    }
}

/// Converts a HashMap<String, serde_json::Value> to Vec<KeyValue> for OpenTelemetry attributes.
pub fn parse_attributes(attributes: Option<&HashMap<String, JsonValue>>) -> Vec<KeyValue> {
    let mut result = Vec::new();
    let Some(attributes) = attributes else {
        return result;
    };

    for (key, value) in attributes {
        match value {
            JsonValue::Bool(b) => result.push(KeyValue::new(key.clone(), *b)),
            JsonValue::String(s) => result.push(KeyValue::new(key.clone(), s.clone())),
            JsonValue::Number(n) => {
                if let Some(i) = n.as_i64() {
                    result.push(KeyValue::new(key.clone(), i));
                } else if let Some(f) = n.as_f64() {
                    result.push(KeyValue::new(key.clone(), f));
                }
            }
            JsonValue::Array(arr) => {
                if arr.len() == 1 {
                    // Treat single-element array as scalar
                    if let Some(single) = arr.first() {
                        match single {
                            JsonValue::Bool(b) => result.push(KeyValue::new(key.clone(), *b)),
                            JsonValue::String(s) => {
                                result.push(KeyValue::new(key.clone(), s.clone()))
                            }
                            JsonValue::Number(n) => {
                                if let Some(i) = n.as_i64() {
                                    result.push(KeyValue::new(key.clone(), i));
                                } else if let Some(f) = n.as_f64() {
                                    result.push(KeyValue::new(key.clone(), f));
                                }
                            }
                            _ => {}
                        }
                    }
                } else if let Some(first) = arr.first() {
                    match first {
                        JsonValue::Bool(_) => {
                            let parsed: Vec<bool> =
                                arr.iter().filter_map(|v| v.as_bool()).collect();
                            parsed.iter().enumerate().for_each(|(index, value)| {
                                result.push(KeyValue::new(format!("{key}.{index}"), *value));
                            });
                        }
                        JsonValue::String(_) => {
                            let parsed: Vec<String> = arr
                                .iter()
                                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                                .collect();
                            parsed.iter().enumerate().for_each(|(index, value)| {
                                result.push(KeyValue::new(format!("{key}.{index}"), value.clone()));
                            });
                        }
                        JsonValue::Number(_) => {
                            // Try as i64, then as f64
                            if arr.iter().all(|v| v.is_i64()) {
                                let parsed: Vec<i64> =
                                    arr.iter().filter_map(|v| v.as_i64()).collect();
                                parsed.iter().enumerate().for_each(|(index, value)| {
                                    result.push(KeyValue::new(format!("{key}.{index}"), *value));
                                });
                            } else if arr.iter().all(|v| v.is_f64() || v.is_i64()) {
                                let parsed: Vec<f64> =
                                    arr.iter().filter_map(|v| v.as_f64()).collect();
                                parsed.iter().enumerate().for_each(|(index, value)| {
                                    result.push(KeyValue::new(format!("{key}.{index}"), *value));
                                });
                            }
                        }
                        _ => {}
                    }
                }
            }
            _ => {}
        }
    }
    result
}

/// Like [`parse_attributes`], but keeps arrays as native OTel arrays instead of
/// flattening them to `key.N`. Used for span events and links, whose attributes the
/// tracer serializes with their original types. Values the OTel API can't represent
/// (mixed or nested arrays, integers beyond 64 bits) are dropped.
pub fn parse_attributes_native(attributes: Option<&HashMap<String, JsonValue>>) -> Vec<KeyValue> {
    let Some(attributes) = attributes else {
        return Vec::new();
    };
    attributes
        .iter()
        .filter_map(|(key, value)| json_to_otel_value(value).map(|v| KeyValue::new(key.clone(), v)))
        .collect()
}

fn json_number_to_otel(n: &serde_json::Number) -> Option<opentelemetry::Value> {
    if let Some(i) = n.as_i64() {
        return Some(i.into());
    }
    let f = n.as_f64()?;
    // serde_json reads integer literals that don't fit in 64 bits as floats.
    if f.fract() == 0.0 && f.abs() >= 9.223_372_036_854_776e18 {
        return None;
    }
    Some(f.into())
}

fn json_to_otel_value(value: &JsonValue) -> Option<opentelemetry::Value> {
    use opentelemetry::{Array, StringValue, Value};
    match value {
        JsonValue::Bool(b) => Some((*b).into()),
        JsonValue::String(s) => Some(s.clone().into()),
        JsonValue::Number(n) => json_number_to_otel(n),
        JsonValue::Array(items) if !items.is_empty() => {
            if let Some(v) = items
                .iter()
                .map(JsonValue::as_bool)
                .collect::<Option<Vec<_>>>()
            {
                Some(Value::Array(Array::Bool(v)))
            } else if let Some(v) = items
                .iter()
                .map(|i| i.as_str().map(|s| StringValue::from(s.to_string())))
                .collect::<Option<Vec<_>>>()
            {
                Some(Value::Array(Array::String(v)))
            } else if let Some(v) = items
                .iter()
                .map(JsonValue::as_i64)
                .collect::<Option<Vec<_>>>()
            {
                Some(Value::Array(Array::I64(v)))
            } else {
                items
                    .iter()
                    .map(|i| match i {
                        JsonValue::Number(n) => match json_number_to_otel(n)? {
                            Value::F64(f) => Some(f),
                            Value::I64(i) => Some(i as f64),
                            _ => None,
                        },
                        _ => None,
                    })
                    .collect::<Option<Vec<_>>>()
                    .map(|v| Value::Array(Array::F64(v)))
            }
        }
        _ => None,
    }
}

pub fn parse_status(code: String, description: String) -> Status {
    match code.to_uppercase().as_str() {
        "OK" => Status::Ok,
        "ERROR" => Status::Error {
            description: description.into(),
        },
        _ => Status::Unset,
    }
}

/// Formats a trace state as a comma-separated key=value string.
/// You may need to adapt this to your actual TraceState type.
pub fn format_trace_state(trace_state: &HashMap<String, String>) -> String {
    trace_state
        .iter()
        .map(|(k, v)| format!("{}={}", k, v))
        .collect::<Vec<_>>()
        .join(",")
}

// --- Metrics DTOs ---

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelGetMeterArgs {
    pub name: String,
    pub version: Option<String>,
    pub schema_url: Option<String>,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelGetMeterReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateCounterArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateCounterReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCounterAddArgs {
    pub meter_name: String,
    pub name: String,
    pub unit: String,
    pub description: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCounterAddReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateUpDownCounterArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateUpDownCounterReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelUpDownCounterAddArgs {
    pub meter_name: String,
    pub name: String,
    pub unit: String,
    pub description: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelUpDownCounterAddReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateGaugeArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateGaugeReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelGaugeRecordArgs {
    pub meter_name: String,
    pub name: String,
    pub unit: String,
    pub description: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelGaugeRecordReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateHistogramArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateHistogramReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelHistogramRecordArgs {
    pub meter_name: String,
    pub name: String,
    pub unit: String,
    pub description: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelHistogramRecordReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateAsynchronousCounterArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateAsynchronousCounterReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateAsynchronousUpDownCounterArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateAsynchronousUpDownCounterReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateAsynchronousGaugeArgs {
    pub meter_name: String,
    pub name: String,
    pub description: String,
    pub unit: String,
    pub value: serde_json::Number,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateAsynchronousGaugeReturn {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelMetricsForceFlushArgs {}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelMetricsForceFlushReturn {
    pub success: bool,
}

// --- Logs DTOs ---

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateLoggerArgs {
    pub name: String,
    pub level: String,
    pub version: Option<String>,
    pub schema_url: Option<String>,
    pub attributes: Option<HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelCreateLoggerReturn {
    pub success: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelWriteLogArgs {
    pub logger_name: String,
    pub level: String,
    pub message: String,
    pub span_id: Option<u64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelWriteLogReturn {
    pub success: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OtelLogsFlushReturn {
    pub success: bool,
    pub message: String,
}
