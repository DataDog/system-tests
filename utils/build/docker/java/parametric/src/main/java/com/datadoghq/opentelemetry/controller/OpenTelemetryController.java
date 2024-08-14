package com.datadoghq.opentelemetry.controller;

import static com.datadoghq.ApmTestClient.LOGGER;
import static io.opentelemetry.api.trace.SpanKind.CLIENT;
import static io.opentelemetry.api.trace.SpanKind.CONSUMER;
import static io.opentelemetry.api.trace.SpanKind.INTERNAL;
import static io.opentelemetry.api.trace.SpanKind.PRODUCER;
import static io.opentelemetry.api.trace.SpanKind.SERVER;
import static java.util.concurrent.TimeUnit.MICROSECONDS;

import com.datadoghq.opentelemetry.dto.AddEventArgs;
import com.datadoghq.opentelemetry.dto.EndSpanArgs;
import com.datadoghq.opentelemetry.dto.FlushArgs;
import com.datadoghq.opentelemetry.dto.FlushResult;
import com.datadoghq.opentelemetry.dto.IsRecordingArgs;
import com.datadoghq.opentelemetry.dto.IsRecordingResult;
import com.datadoghq.opentelemetry.dto.RecordExceptionArgs;
import com.datadoghq.opentelemetry.dto.SetAttributesArgs;
import com.datadoghq.opentelemetry.dto.SetNameArgs;
import com.datadoghq.opentelemetry.dto.SetStatusArgs;
import com.datadoghq.opentelemetry.dto.SpanContextArgs;
import com.datadoghq.opentelemetry.dto.SpanContextResult;
import com.datadoghq.opentelemetry.dto.SpanLink;
import com.datadoghq.opentelemetry.dto.StartSpanArgs;
import com.datadoghq.opentelemetry.dto.StartSpanResult;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.GlobalTracer;
import datadog.trace.api.internal.InternalTracer;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.TraceFlags;
import io.opentelemetry.api.trace.TraceState;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapPropagator;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping(value = "/trace/otel", consumes = "application/json", produces = "application/json")
public class OpenTelemetryController {
  private final Tracer tracer;
  private final TextMapPropagator propagator;
  private final Map<Long, Span> spans;

  public OpenTelemetryController() {
    this.tracer = GlobalOpenTelemetry.getTracer("java-client");
    this.propagator = GlobalOpenTelemetry.getPropagators().getTextMapPropagator();
    this.spans = new HashMap<>();
  }

  private static SpanKind parseSpanKindNumber(int spanKindNumber) {
    return switch (spanKindNumber) {
      case 1 -> INTERNAL;
      case 2 -> SERVER;
      case 3 -> CLIENT;
      case 4 -> PRODUCER;
      case 5 -> CONSUMER;
      default -> null;
    };
  }

  private static Attributes parseAttributes(Map<String, Object> attributes) {
    AttributesBuilder builder = Attributes.builder();
    for (Map.Entry<String, Object> entry : attributes.entrySet()) {
      String key = entry.getKey();
      Object value = entry.getValue();
      if (value instanceof Boolean) {
        builder.put(key, (Boolean) value);
      } else if (value instanceof String) {
        builder.put(key, (String) value);
      } else if (value instanceof Long) {
        builder.put(key, (Long) value);
      } else if (value instanceof Double) {
        builder.put(key, (Double) value);
      } else if (value instanceof Collection<?> values && !values.isEmpty()) {
        Object firstValue = values.iterator().next();
        if (firstValue instanceof Boolean) {
          values.forEach(v -> builder.put(key, (Boolean) v));
        } else if (firstValue instanceof String) {
          values.forEach(v -> builder.put(key, (String) v));
        } else if (firstValue instanceof Long) {
          values.forEach(v -> builder.put(key, (Long) v));
        } else if (firstValue instanceof Double) {
          values.forEach(v -> builder.put(key, (Double) v));
        }
      }
    }
    return builder.build();
  }

  private static String formatTraceFlags(TraceFlags traceFlags) {
    return Integer.toBinaryString(traceFlags.asByte());
  }

  private static String formatTraceState(TraceState traceState) {
    StringBuilder builder = new StringBuilder();
    traceState.forEach((memberKey, memberValue) -> {
      if (!builder.isEmpty()) {
        builder.append(',');
      }
      builder.append(memberKey).append('=').append(memberValue);
    });
    return builder.toString();
  }

  @PostMapping("start_span")
  public StartSpanResult startSpan(@RequestBody StartSpanArgs args) {
    LOGGER.info("Starting OTel span: {}", args);
    // Build span from request
    SpanBuilder builder = this.tracer.spanBuilder(args.name());
    // Check parent span to create parent context from
    if (args.parentId() != 0L) {
      Span parentSpan = getSpan(args.parentId());
      if (parentSpan != null) {
        Context contextWithParentSpan = parentSpan.storeInContext(Context.root());
        builder.setParent(contextWithParentSpan);
      }
    }
    // Check HTTP headers to extract propagated context from
    if (args.httpHeaders() != null && !args.httpHeaders().isEmpty()) {
      Context extractedContext = this.propagator.extract(
          Context.root(),
          args.httpHeaders(),
          HeadersTextMapGetter.INSTANCE
      );
      builder.setParent(extractedContext);
    }
    // Add other span information
    builder.setSpanKind(parseSpanKindNumber(args.spanKind()));
    if (args.timestamp() > 0) {
      builder.setStartTimestamp(args.timestamp(), MICROSECONDS);
    }
    if (args.links() != null && !args.links().isEmpty()) {
      for (SpanLink spanLink : args.links()) {
        SpanContext spanContext = null;
        LOGGER.warn("Span link: {}", spanLink);
        if (spanLink.parentId() > 0) {
          LOGGER.warn("Parent id found");
          Span span = getSpan(spanLink.parentId());
          if (span == null) {
            return StartSpanResult.error();
          }
          LOGGER.warn("Parent span found");
          spanContext = span.getSpanContext();
        } else if (spanLink.httpHeaders() != null && !spanLink.httpHeaders().isEmpty()) {
          Context extractedContext = this.propagator.extract(
              Context.root(),
              spanLink.httpHeaders(),
              HeadersTextMapGetter.INSTANCE
          );
          spanContext = Span.fromContext(extractedContext).getSpanContext();
          LOGGER.warn("Extracted context {} | valid {}", spanContext, spanContext.isValid());
        }
        if (spanContext != null && spanContext.isValid()) {
          if (spanLink.attributes() != null && !spanLink.attributes().isEmpty()) {
            LOGGER.warn("Adding links with attributes {}", spanContext);
            builder.addLink(spanContext, parseAttributes(spanLink.attributes()));
          } else {
            LOGGER.warn("Adding link without attributes {}", spanContext);
            builder.addLink(spanContext);
          }
        }
      }
    }
    if (args.attributes() != null && !args.attributes().isEmpty()) {
      builder.setAllAttributes(parseAttributes(args.attributes()));
    }
    Span span = builder.startSpan();
    // Store span
    long traceId = DDTraceId.fromHex(span.getSpanContext().getTraceId()).toLong();
    long spanId = DDSpanId.fromHex(span.getSpanContext().getSpanId());
    this.spans.put(spanId, span);
    // Return result
    return new StartSpanResult(spanId, traceId);
  }

  @PostMapping("span_context")
  public SpanContextResult getSpanContext(@RequestBody SpanContextArgs args) {
    LOGGER.info("Getting OTel span context: {}", args);
    Span span = getSpan(args.spanId());
    if (span == null) {
      return SpanContextResult.error();
    }
    SpanContext spanContext = span.getSpanContext();
    return new SpanContextResult(
        spanContext.getSpanId(),
        spanContext.getTraceId(),
        formatTraceFlags(spanContext.getTraceFlags()),
        formatTraceState(spanContext.getTraceState()),
        spanContext.isRemote()
    );
  }

  @PostMapping("is_recording")
  public IsRecordingResult isRecording(@RequestBody IsRecordingArgs args) {
    LOGGER.info("Checking whether OTel span is recording: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      return new IsRecordingResult(span.isRecording());
    } else {
      return new IsRecordingResult(false);
    }
  }

  @PostMapping("set_name")
  public void setName(@RequestBody SetNameArgs args) {
    LOGGER.info("Setting OTel span name: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.updateName(args.name());
    }
  }

  @PostMapping("set_status")
  public void setStatus(@RequestBody SetStatusArgs args) {
    LOGGER.info("Setting OTel span status: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.setStatus(args.code(), args.description());
    }
  }

  @PostMapping("set_attributes")
  public void setAttributes(@RequestBody SetAttributesArgs args) {
    LOGGER.info("Setting OTel span attributes: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.setAllAttributes(parseAttributes(args.attributes()));
    }
  }

  @PostMapping("add_event")
  public void addEvent(@RequestBody AddEventArgs args) {
    LOGGER.info("Adding OTel span event: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.addEvent(args.name(), parseAttributes(args.attributes()), args.timestamp(), MICROSECONDS);
    }
  }

  @PostMapping("record_exception")
  public void recordException(@RequestBody RecordExceptionArgs args) {
    LOGGER.info("Recording OTel span exception: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.recordException(new Exception(args.message()), parseAttributes(args.attributes()));
    }
  }

  @PostMapping("end_span")
  public void endSpan(@RequestBody EndSpanArgs args) {
    LOGGER.info("Ending OTel span: {}", args);
    Span span = getSpan(args.id());
    if (span != null) {
      if (args.timestamp() > 0) {
        span.end(args.timestamp(), MICROSECONDS);
      } else {
        span.end();
      }
    }
  }

  @PostMapping("flush")
  public FlushResult flush(@RequestBody FlushArgs args) {
    LOGGER.info("Flushing OTel spans: {}", args);
    try {
      ((InternalTracer) GlobalTracer.get()).flush();
      this.spans.clear();
      return new FlushResult(true);
    } catch (Exception e) {
      LOGGER.warn("Failed to flush OTel spans", e);
      return new FlushResult(false);
    }
  }

  private Span getSpan(long spanId) {
    Span span = this.spans.get(spanId);
    if (span == null) {
      LOGGER.warn("OTel span {} does not exist.", spanId);
    }
    return span;
  }

  void clearSpans() {
    this.spans.clear();
  }

  private static class HeadersTextMapGetter implements TextMapGetter<Map<String, String>> {
    private static final HeadersTextMapGetter INSTANCE = new HeadersTextMapGetter();

    @Override
    public Iterable<String> keys(Map<String, String> headers) {
      return headers.keySet();
    }

    @Override
    public String get(Map<String, String> headers, String key) {
      if (headers == null) {
        return null;
      }
      return headers.get(key);
    }
  }
}
