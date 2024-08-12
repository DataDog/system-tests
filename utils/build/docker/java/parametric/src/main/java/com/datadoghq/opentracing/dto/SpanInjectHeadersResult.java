package com.datadoghq.opentracing.dto;

import java.util.Map;

public record SpanInjectHeadersResult(Map<String, String> headers) {
}
