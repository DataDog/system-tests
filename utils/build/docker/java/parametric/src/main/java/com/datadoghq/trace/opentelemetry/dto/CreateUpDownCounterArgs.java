package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record CreateUpDownCounterArgs(
    @JsonProperty("meter_name") String meterName, String name, String description, String unit) {}
