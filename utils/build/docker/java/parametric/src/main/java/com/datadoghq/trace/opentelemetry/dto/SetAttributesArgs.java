package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record SetAttributesArgs(
    @JsonProperty("span_id") long spanId,
    Map<String, Object> attributes) {
}
