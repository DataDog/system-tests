package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public record SetAsynchronousObservationsArgs(
    @JsonProperty("meter_name") String meterName,
    String kind,
    String name,
    String unit,
    String description,
    List<Observation> observations) {
  public record Observation(Number value, Map<String, String> attributes) {}
}
