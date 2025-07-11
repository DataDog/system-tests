package com.datadoghq.trace.opentracing.dto;

import java.util.Map;

public record SpanGetAllBaggageResult(
        Map<String, String> baggage) {
}
