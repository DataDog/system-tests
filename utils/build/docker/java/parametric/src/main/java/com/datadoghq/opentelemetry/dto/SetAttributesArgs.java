package com.datadoghq.opentelemetry.dto;

import java.util.Map;

public record SetAttributesArgs(long spanId, Map<String, Object> attributes) {
}
