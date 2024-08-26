package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record StartSpanResult(
    @JsonProperty("span_id") long spanId,
    @JsonProperty("trace_id") long traceId) {
  public static StartSpanResult error(){
    return new StartSpanResult(0L, 0L);
  }
}
