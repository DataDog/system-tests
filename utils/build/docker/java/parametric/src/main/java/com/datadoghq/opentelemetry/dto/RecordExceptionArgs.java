package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record RecordExceptionArgs(
    @JsonProperty("span_id") long spanId,
    String message,
    Map<String, Object> attributes) {
}
