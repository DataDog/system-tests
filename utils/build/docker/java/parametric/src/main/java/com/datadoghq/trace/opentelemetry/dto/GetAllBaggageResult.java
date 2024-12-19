package com.datadoghq.trace.opentelemetry.dto;

import java.util.Map;

public record GetAllBaggageResult(
        Map<String, String> baggage) {
}
