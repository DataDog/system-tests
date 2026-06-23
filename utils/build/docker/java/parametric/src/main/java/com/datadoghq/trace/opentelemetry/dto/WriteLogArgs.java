package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record WriteLogArgs(
    @JsonProperty("logger_name") String loggerName,
    String level,
    String message,
    @JsonProperty("span_id") long spanId) {}
