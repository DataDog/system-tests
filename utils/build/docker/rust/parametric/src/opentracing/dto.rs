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
