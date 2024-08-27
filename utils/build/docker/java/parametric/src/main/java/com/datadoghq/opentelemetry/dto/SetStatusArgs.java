package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.opentelemetry.api.trace.StatusCode;

public record SetStatusArgs(
    @JsonProperty("span_id") long spanId,
    StatusCode code,
    String description) {
}
