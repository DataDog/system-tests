package com.datadoghq.trace.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import datadog.trace.api.llmobs.LLMObs;
import datadog.trace.api.llmobs.LLMObsSpan;
import io.opentracing.Scope;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(value = "/llm_observability")
public class LlmObsController {

  @PostMapping("trace")
  @SuppressWarnings("unchecked")
  public Map<String, Object> trace(@RequestBody Map<String, Object> body) {
    try {
      Object request = body.get("trace_structure_request");
      if (request instanceof Map) {
        createTrace((Map<String, Object>) request);
      }
    } catch (Exception e) {
      LOGGER.error("Error creating LLMObs trace", e);
    }
    return Collections.emptyMap();
  }

  @SuppressWarnings("unchecked")
  private void createTrace(Map<String, Object> traceStructure) {
    String type = (String) traceStructure.getOrDefault("type", "span");

    if ("annotation_context".equals(type)) {
      // annotation_context is not supported in the Java SDK; just run children directly
      List<Map<String, Object>> children = (List<Map<String, Object>>) traceStructure.get("children");
      if (children != null) {
        for (Map<String, Object> child : children) {
          createTrace(child);
        }
      }
      return;
    }

    String sdk = (String) traceStructure.getOrDefault("sdk", "llmobs");
    boolean isLlmObs = "llmobs".equals(sdk);
    String name = (String) traceStructure.getOrDefault("name", "");
    boolean annotateAfter = Boolean.TRUE.equals(traceStructure.get("annotate_after"));
    List<Map<String, Object>> annotations = (List<Map<String, Object>>) traceStructure.get("annotations");
    List<Map<String, Object>> children = (List<Map<String, Object>>) traceStructure.get("children");

    if (isLlmObs) {
      String kind = (String) traceStructure.get("kind");
      String modelName = (String) traceStructure.get("model_name");
      String modelProvider = (String) traceStructure.get("model_provider");
      String mlApp = (String) traceStructure.get("ml_app");
      String sessionId = (String) traceStructure.get("session_id");

      LLMObsSpan span = startLLMObsSpan(kind, name, modelName, modelProvider, mlApp, sessionId);

      if (children != null) {
        for (Map<String, Object> child : children) {
          createTrace(child);
        }
      }

      if (annotateAfter) {
        span.finish();
        applyAnnotations(span, kind, annotations);
      } else {
        applyAnnotations(span, kind, annotations);
        span.finish();
      }
    } else {
      Span span = GlobalTracer.get().buildSpan(name).start();
      try (Scope scope = GlobalTracer.get().scopeManager().activate(span)) {
        if (children != null) {
          for (Map<String, Object> child : children) {
            createTrace(child);
          }
        }
      } finally {
        span.finish();
      }
    }
  }

  private LLMObsSpan startLLMObsSpan(
      String kind,
      String name,
      String modelName,
      String modelProvider,
      String mlApp,
      String sessionId) {
    if (kind == null) {
      throw new IllegalArgumentException("LLMObs span kind is required");
    }
    switch (kind) {
      case "llm":
        return LLMObs.startLLMSpan(name, modelName, modelProvider, mlApp, sessionId);
      case "task":
        return LLMObs.startTaskSpan(name, mlApp, sessionId);
      case "agent":
        return LLMObs.startAgentSpan(name, mlApp, sessionId);
      case "workflow":
        return LLMObs.startWorkflowSpan(name, mlApp, sessionId);
      case "tool":
        return LLMObs.startToolSpan(name, mlApp, sessionId);
      default:
        throw new IllegalArgumentException("Unsupported LLMObs span kind: " + kind);
    }
  }

  @SuppressWarnings("unchecked")
  private void applyAnnotations(
      LLMObsSpan span, String kind, List<Map<String, Object>> annotations) {
    if (annotations == null) {
      return;
    }

    for (Map<String, Object> annotation : annotations) {
      Object inputDataObj = annotation.get("input_data");
      Object outputDataObj = annotation.get("output_data");

      if (inputDataObj != null || outputDataObj != null) {
        if ("llm".equals(kind) && (inputDataObj instanceof List || outputDataObj instanceof List)) {
          span.annotateIO(parseMessages(inputDataObj), parseMessages(outputDataObj));
        } else {
          String inputStr = inputDataObj instanceof String ? (String) inputDataObj : "";
          String outputStr = outputDataObj instanceof String ? (String) outputDataObj : "";
          span.annotateIO(inputStr, outputStr);
        }
      }

      Map<String, Object> metadata = (Map<String, Object>) annotation.get("metadata");
      if (metadata != null) {
        span.setMetadata(metadata);
      }

      Map<String, Object> metricsRaw = (Map<String, Object>) annotation.get("metrics");
      if (metricsRaw != null) {
        Map<String, Number> metrics = new HashMap<>();
        metricsRaw.forEach(
            (k, v) -> {
              if (v instanceof Number) metrics.put(k, (Number) v);
            });
        span.setMetrics(metrics);
      }

      Map<String, Object> tags = (Map<String, Object>) annotation.get("tags");
      if (tags != null) {
        span.setTags(tags);
      }
    }
  }

  @SuppressWarnings("unchecked")
  private List<LLMObs.LLMMessage> parseMessages(Object data) {
    List<LLMObs.LLMMessage> messages = new ArrayList<>();
    if (data == null) {
      return messages;
    }
    List<?> list = data instanceof List ? (List<?>) data : Collections.singletonList(data);
    for (Object item : list) {
      if (item instanceof Map) {
        Map<String, Object> msg = (Map<String, Object>) item;
        String role = (String) msg.getOrDefault("role", "");
        String content = (String) msg.getOrDefault("content", "");
        messages.add(LLMObs.LLMMessage.from(role, content));
      }
    }
    return messages;
  }
}
