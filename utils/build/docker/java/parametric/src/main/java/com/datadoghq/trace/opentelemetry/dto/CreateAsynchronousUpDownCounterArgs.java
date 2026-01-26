package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record CreateAsynchronousUpDownCounterArgs(
    @JsonProperty("meter_name") String meterName,
    String name,
    String description,
    String unit,
    Number value,
    Map<String, String> attributes) {}
