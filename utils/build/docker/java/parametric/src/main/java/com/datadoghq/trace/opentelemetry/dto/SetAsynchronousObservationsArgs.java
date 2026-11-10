package com.datadoghq.trace.opentelemetry.dto;

import java.util.List;
import java.util.Map;

public record SetAsynchronousObservationsArgs(String name, List<Observation> observations) {
  public record Observation(Number value, Map<String, String> attributes) {}
}
