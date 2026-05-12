package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record GetMeterArgs(
    String name,
    String version,
    @JsonProperty("schema_url") String schemaUrl,
    Map<String, String> attributes) {}
