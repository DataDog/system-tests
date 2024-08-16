package com.datadoghq.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanSetMetaArgs(@JsonProperty("span_id") long spanId, String key, String value) {
}
