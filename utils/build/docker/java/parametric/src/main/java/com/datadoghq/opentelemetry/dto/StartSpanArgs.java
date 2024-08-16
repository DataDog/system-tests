package com.datadoghq.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public record StartSpanArgs(
    @JsonProperty("parent_id") long parentId,
    String name,
    @JsonProperty("span_kind") int spanKind,
    long timestamp,
    @JsonProperty("http_headers") List<List<String>> httpHeaders,
    List<SpanLink> links,
    Map<String, Object> attributes) {
}
