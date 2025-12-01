package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record SpanLink(
    @JsonProperty("parent_id") long parentId,
    Map<String, Object> attributes) {
}
