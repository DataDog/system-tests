package com.datadoghq.opentracing.dto;

public record SpanSetMetaArgs(long spanId, String key, String value) {
}
