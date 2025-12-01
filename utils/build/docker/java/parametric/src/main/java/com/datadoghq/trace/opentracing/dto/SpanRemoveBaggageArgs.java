package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanRemoveBaggageArgs(
        @JsonProperty("span_id") long spanId,
        String key) {
}

