package com.datadoghq.trace.dto;

import java.util.HashMap;
import java.util.Map;

public record GetTraceConfigResult(Map<String, String> config) {
  public static GetTraceConfigResult error(){
    return new GetTraceConfigResult(new HashMap<>());
  }
}
