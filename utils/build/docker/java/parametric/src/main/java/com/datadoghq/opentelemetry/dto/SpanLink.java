package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public record SpanLink(
    @JsonProperty("parent_id") long parentId,
    Map<String, Object> attributes,
    @JsonProperty("http_headers") List<List<String>> httpHeaders) {
}
