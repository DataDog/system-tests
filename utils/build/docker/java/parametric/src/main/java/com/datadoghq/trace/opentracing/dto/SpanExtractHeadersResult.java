package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanExtractHeadersResult(@JsonProperty("span_id") Long spanId) {
}
