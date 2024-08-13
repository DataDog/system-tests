package com.datadoghq.opentelemetry.dto;

public record SetNameArgs(long spanId, String name) {
}
