package com.datadoghq.trace.opentracing.dto;

import com.datadoghq.trace.opentracing.dto.KeyValue.KeyValueListDeserializer;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import java.util.List;

public record StartSpanArgs(
    @JsonProperty("parent_id") long parentId,
    String name,
    String service,
    String type,
    String resource,
    String origin,
    @JsonProperty("http_headers") @JsonDeserialize(using = KeyValueListDeserializer.class) List<KeyValue> headers,
    List<SpanLinks> links,
    @JsonProperty("span_tags") @JsonDeserialize(using = KeyValueListDeserializer.class) List<KeyValue> tags) {
}
