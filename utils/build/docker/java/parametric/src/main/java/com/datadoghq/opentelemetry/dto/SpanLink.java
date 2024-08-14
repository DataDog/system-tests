package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record SpanLink(
    @JsonProperty("span_id") long parentId,
    Map<String, Object> attributes,
    Map<String, String> httpHeaders) {
}
