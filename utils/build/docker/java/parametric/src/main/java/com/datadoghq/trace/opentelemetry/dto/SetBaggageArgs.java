package com.datadoghq.trace.opentelemetry.dto;

public record SetBaggageArgs(
        String key,
        String value) {
}

