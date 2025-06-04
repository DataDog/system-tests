package com.datadoghq.trace.opentracing.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SpanRecordExceptionResult(@JsonProperty("exception_type") String exceptionType) {
    public static SpanRecordExceptionResult error() {
        return new SpanRecordExceptionResult(null);
    }
}