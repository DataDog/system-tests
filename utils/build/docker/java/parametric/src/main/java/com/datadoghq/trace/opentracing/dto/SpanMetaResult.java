package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanMetaResult(
    @JsonProperty("http_url") String httpUrl 
    // add any other meta fields...
    ) {
public static SpanMetaResult error() {
    return new SpanMetaResult("");
  }
}
