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
    pub code: i32,
    pub description: Option<String>,
}

// --- SpanContextArgs ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SpanContextArgs {
    pub span_id: u64,
}

// --- SpanContextResult ---
#[derive(Debug, Serialize, Deserialize)]
pub struct SpanContextResult {
    pub span_id: String,
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

pub fn system_time_from_millis(millis: i64) -> SystemTime {
    if millis >= 0 {
        UNIX_EPOCH + Duration::from_millis(millis as u64)
    } else {
        UNIX_EPOCH - Duration::from_millis((-millis) as u64)
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

pub fn parse_status(code: i32, description: Option<String>) -> Status {
    match code {
        1 => Status::Ok,
        2 => Status::Error {
            description: description.unwrap_or_default().into(),
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
