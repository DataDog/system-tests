package com.datadoghq.opentelemetry.dto;

import java.util.Map;

public record RecordExceptionArgs(long spanId, String message, Map<String, Object> attributes) {
}
