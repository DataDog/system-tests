package com.datadoghq.opentelemetry.dto;

import com.datadoghq.opentelemetry.dto.KeyValue.KeyValueListDeserializer;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import java.util.List;
import java.util.Map;

public record StartSpanArgs(
    @JsonProperty("parent_id") long parentId,
    String name,
    @JsonProperty("span_kind") int spanKind,
    long timestamp,
    @JsonProperty("http_headers") @JsonDeserialize(using = KeyValueListDeserializer.class) List<KeyValue> httpHeaders,
    List<SpanLink> links,
    Map<String, Object> attributes) {
}
