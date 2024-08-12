package com.datadoghq.opentracing.dto;

public record SpanSetMetricArgs(long spanId, String key, float value) {
}
