package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanExtractHeadersResult(@JsonProperty("span_id") long spanId) {
  public static SpanExtractHeadersResult error() {
    return new SpanExtractHeadersResult(0L);
  }
}
