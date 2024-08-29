package com.datadoghq.trace.opentracing.dto;

import com.datadoghq.trace.opentracing.dto.KeyValue.KeyValueListSerializer;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import java.util.List;

public record SpanInjectHeadersResult(
    @JsonProperty("http_headers") @JsonSerialize(using = KeyValueListSerializer.class) List<KeyValue> httpHeaders) {
}
