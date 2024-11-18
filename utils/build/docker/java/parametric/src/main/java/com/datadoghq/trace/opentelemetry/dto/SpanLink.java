package com.datadoghq.trace.opentelemetry.dto;

import com.datadoghq.trace.opentelemetry.dto.KeyValue.KeyValueListDeserializer;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import java.util.List;
import java.util.Map;

public record SpanLink(
    @JsonProperty("parent_id") long parentId,
    Map<String, Object> attributes {
}
