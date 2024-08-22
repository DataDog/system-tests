package com.datadoghq.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanErrorArgs(@JsonProperty("span_id") long spanId, String type, String message, String stack) {
}
