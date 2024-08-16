package com.datadoghq.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record SpanInjectHeadersResult( @JsonProperty("http_headers") List<HttpHeader> httpHeaders) {
}
