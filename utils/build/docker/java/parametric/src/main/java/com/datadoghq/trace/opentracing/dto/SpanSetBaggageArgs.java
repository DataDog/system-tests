package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanSetBaggageArgs(
        @JsonProperty("span_id") long spanId,
        String key,
        String value) {
}

