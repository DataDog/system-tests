package com.datadoghq.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record StartSpanArgs(
    @JsonProperty("parent_id") long parentId,
    String name,
    String service,
    String type,
    String resource,
    String origin,
    @JsonProperty("http_headers") List<HttpHeader> headers,
    List<SpanLinks> links) {
}
