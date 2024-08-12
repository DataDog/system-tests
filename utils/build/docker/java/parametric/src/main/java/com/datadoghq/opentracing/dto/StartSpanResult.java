package com.datadoghq.opentracing.dto;

public record StartSpanResult(long traceId, long spanId) {
  public static StartSpanResult error() {
    return new StartSpanResult(0L, 0L);
  }
}
