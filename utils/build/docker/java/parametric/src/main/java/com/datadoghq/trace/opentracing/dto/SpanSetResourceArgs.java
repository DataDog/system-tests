package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanSetResourceArgs(@JsonProperty("span_id") long spanId, String resource) {
}
