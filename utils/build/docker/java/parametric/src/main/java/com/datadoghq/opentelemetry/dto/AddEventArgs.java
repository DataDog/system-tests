package com.datadoghq.opentelemetry.dto;

import java.util.Map;

public record AddEventArgs(long spanId, String name, long timestamp, Map<String, Object> attributes) {
}
