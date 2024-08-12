package com.datadoghq.opentracing.dto;

import java.util.Map;

public record StartSpanArgs(long parentId, String name, String service, String type, String resource, String origin,
                            Map<String, String> headers, Map<String, String> links) {
}
