package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanExtractHeadersResult(@JsonProperty("span_id") Long spanId) {
  public static SpanExtractHeadersResult error() {
    // Expected to return no span identifier of error
    return new SpanExtractHeadersResult(null);
  }
}
