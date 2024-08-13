package com.datadoghq.opentelemetry.dto;

import io.opentelemetry.api.trace.StatusCode;

public record SetStatusArgs(long spanId, StatusCode code, String description) {
}
