package com.datadoghq.trace.opentracing.dto;

import com.datadoghq.trace.opentracing.dto.KeyValue.KeyValueListDeserializer;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import java.util.List;

public record SpanExtractHeadersArgs(
    @JsonProperty("http_headers") @JsonDeserialize(using = KeyValueListDeserializer.class) List<KeyValue> headers) {
}
