package com.datadoghq.trace.metrics.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import datadog.trace.api.GlobalTracer;
import datadog.trace.api.internal.InternalTracer;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(value = "/trace/stats")
public class MetricsController {
  @PostMapping("flush")
  public void flush() {
    LOGGER.info("Flushing metrics");
    try {
      ((InternalTracer) GlobalTracer.get()).flushMetrics();
    } catch (Exception e) {
      LOGGER.warn("Failed to flush metrics", e);
    }
  }
}
