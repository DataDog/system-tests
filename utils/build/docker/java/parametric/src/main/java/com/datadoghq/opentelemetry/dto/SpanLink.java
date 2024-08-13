package com.datadoghq.opentelemetry.dto;

import java.util.Map;

public record SpanLink(long parentId, Map<String, Object> attributes, Map<String, String> httpHeaders) {
}
