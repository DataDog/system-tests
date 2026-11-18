package com.datadoghq.trace.dsm.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import com.datadoghq.trace.dsm.dto.DsmProduceCheckpointArgs;
import datadog.trace.api.experimental.DataStreamsCheckpointer;
import datadog.trace.api.experimental.DataStreamsContextCarrier;
import io.opentracing.Scope;
import io.opentracing.Span;
import io.opentracing.Tracer;
import io.opentracing.util.GlobalTracer;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(value = "/trace/dsm")
public class DataStreamsController {

  @PostMapping("produce_checkpoint")
  public void produceCheckpoint(@RequestBody DsmProduceCheckpointArgs args) {
    LOGGER.info("Setting DSM produce checkpoint: {}", args);
    // The checkpoint is ignored without an active span.
    Tracer tracer = GlobalTracer.get();
    Span span = tracer.buildSpan("dsm.produce").start();
    try (Scope scope = tracer.activateSpan(span)) {
      DataStreamsCheckpointer.get().setProduceCheckpoint(args.type(), args.target(), new MapCarrier());
    } finally {
      span.finish();
    }
  }

  private static final class MapCarrier implements DataStreamsContextCarrier {
    private final Map<String, Object> data = new HashMap<>();

    @Override
    public Set<Map.Entry<String, Object>> entries() {
      return data.entrySet();
    }

    @Override
    public void set(String key, String value) {
      data.put(key, value);
    }
  }
}
