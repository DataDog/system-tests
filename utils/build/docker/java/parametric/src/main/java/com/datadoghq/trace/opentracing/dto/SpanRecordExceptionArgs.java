package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record SpanRecordExceptionArgs(@JsonProperty("span_id") long spanId, String message, Map<String, Object> attributes) {
}