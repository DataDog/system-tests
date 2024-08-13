package com.datadoghq.opentelemetry.dto;

import java.util.List;
import java.util.Map;

public record StartSpanArgs(long parentId, String name, int spanKind, long timestamp, Map<String, String> httpHeaders,
                            List<SpanLink> links, Map<String, Object> attributes) {
}
