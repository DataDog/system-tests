package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record AddEventArgs(
    @JsonProperty("span_id") long spanId,
    String name,
    long timestamp,
    Map<String, Object> attributes) {
}
