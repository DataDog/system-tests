package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public record StartSpanArgs(
    @JsonProperty("parent_id") Long parentId,
    String name,
    @JsonProperty("span_kind") Integer spanKind,
    Long timestamp,
    List<SpanLink> links,
    Map<String, Object> attributes) {
}
