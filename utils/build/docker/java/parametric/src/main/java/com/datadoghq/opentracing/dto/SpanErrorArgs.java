package com.datadoghq.opentracing.dto;

public record SpanErrorArgs(long spanId, String type, String message, String stack) {
}
