package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanSetMetricArgs(@JsonProperty("span_id") long spanId, String key, float value) {
}
