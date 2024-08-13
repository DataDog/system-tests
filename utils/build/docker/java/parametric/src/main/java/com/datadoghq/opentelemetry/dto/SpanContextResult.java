package com.datadoghq.opentelemetry.dto;

public record SpanContextResult(String spanId, String traceId, String traceFlags, String traceState, boolean remote) {
  public static SpanContextResult error() {
    return new SpanContextResult("0000000000000000", "00000000000000000000000000000000", "0", "", false);
  }
}
