package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanInjectHeadersArgs(@JsonProperty("span_id") long spanId) {
}
