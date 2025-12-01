package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanGetAllBaggageArgs(
        @JsonProperty("span_id") long spanId) {
}

