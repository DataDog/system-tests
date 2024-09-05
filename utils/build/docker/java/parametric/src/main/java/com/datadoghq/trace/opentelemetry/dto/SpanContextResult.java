package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanContextResult(
    @JsonProperty("span_id") String spanId,
    @JsonProperty("trace_id") String traceId,
    @JsonProperty("trace_flags") String traceFlags,
    @JsonProperty("trace_state") String traceState,
    boolean remote) {
  public static SpanContextResult error() {
    return new SpanContextResult("0000000000000000", "00000000000000000000000000000000", "00", "", false);
  }
}
