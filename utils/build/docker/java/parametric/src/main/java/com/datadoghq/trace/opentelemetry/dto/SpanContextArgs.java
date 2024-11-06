package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanContextArgs(@JsonProperty("span_id") long spanId) {
}
