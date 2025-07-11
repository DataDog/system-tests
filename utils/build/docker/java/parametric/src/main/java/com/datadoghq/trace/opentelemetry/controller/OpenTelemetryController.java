package com.datadoghq.trace.opentelemetry.controller;

import static com.datadoghq.ApmTestClient.LOGGER;
import static com.datadoghq.trace.opentelemetry.controller.OpenTelemetryTypeHelper.formatTraceState;
import static com.datadoghq.trace.opentelemetry.controller.OpenTelemetryTypeHelper.parseAttributes;
import static com.datadoghq.trace.opentelemetry.controller.OpenTelemetryTypeHelper.parseSpanKindNumber;
import static java.util.concurrent.TimeUnit.MICROSECONDS;

import com.datadoghq.trace.opentelemetry.dto.*;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.GlobalTracer;
import datadog.trace.api.internal.InternalTracer;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.baggage.Baggage;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping(value = "/trace/otel")
public class OpenTelemetryController {
  private final Tracer tracer;
  private final Map<Long, Span> spans;
  private Baggage baggage;

  public OpenTelemetryController() {
    this.tracer = GlobalOpenTelemetry.getTracer("java-client");
    this.spans = new HashMap<>();
    this.baggage = Baggage.empty();
  }

  @PostMapping("start_span")
  public StartSpanResult startSpan(@RequestBody StartSpanArgs args) {
    LOGGER.info("Starting OTel span: {}", args);
    // Build span from request
    SpanBuilder builder = this.tracer.spanBuilder(args.name());
    // Check parent span to create parent context from
    if (args.parentId() != null) {
      Span parentSpan = getSpan(args.parentId());
      if (parentSpan != null) {
        Context contextWithParentSpan = parentSpan.storeInContext(Context.root());
        builder.setParent(contextWithParentSpan);
      }
    }
    // Add other span information
    if (args.spanKind() != null) {
      builder.setSpanKind(parseSpanKindNumber(args.spanKind()));
    }
    if (args.timestamp() != null) {
      builder.setStartTimestamp(args.timestamp(), MICROSECONDS);
    }
    if (!args.links().isEmpty()) {
      for (SpanLink spanLink : args.links()) {
        LOGGER.debug("Span link: {}", spanLink);
        Span span = getSpan(spanLink.parentId());
        if (span == null) {
          return StartSpanResult.error();
        }
        SpanContext spanContext = span.getSpanContext();
        if (spanContext != null && spanContext.isValid()) {
          LOGGER.debug("Adding links from context {}", spanContext);
          builder.addLink(spanContext, parseAttributes(spanLink.attributes()));
        }
      }
    }
    builder.setAllAttributes(parseAttributes(args.attributes()));
    Span span = builder.startSpan();
    // Store span
    long traceId = DDTraceId.fromHex(span.getSpanContext().getTraceId()).toLong();
    long spanId = DDSpanId.fromHex(span.getSpanContext().getSpanId());
    this.spans.put(spanId, span);
    // Return result
    return new StartSpanResult(spanId, traceId);
  }

  @GetMapping("current_span")
  public StartSpanResult currentSpan() {
    LOGGER.info("Getting current OTel span");
    Span current = Span.current();
    SpanContext spanContext = current.getSpanContext();
    long traceId = DDTraceId.fromHex(spanContext.getTraceId()).toLong();
    long spanId = DDSpanId.fromHex(spanContext.getSpanId());
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
        spanContext.getTraceFlags().asHex(),
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
      if (args.timestamp() == 0L) {
        span.addEvent(args.name(), parseAttributes(args.attributes()));
      } else {
        span.addEvent(args.name(), parseAttributes(args.attributes()), args.timestamp(), MICROSECONDS);
      }
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
      // Only flush spans when tracing was enabled
      if (GlobalTracer.get() instanceof InternalTracer internalTracer) {
          internalTracer.flush();
      }
      this.spans.clear();
      return new FlushResult(true);
    } catch (Exception e) {
      LOGGER.warn("Failed to flush OTel spans", e);
      return new FlushResult(false);
    }
  }

  @PostMapping("set_baggage")
  public void setBaggage(@RequestBody SetBaggageArgs args) {
    LOGGER.info("Setting OTel baggage: {}", args);
    this.baggage = this.baggage
            .toBuilder()
            .put(args.key(), args.value())
            .build();
  }

  @GetMapping("get_baggage")
  public GetBaggageResult getBaggage(@RequestBody GetBaggageArgs args) {
    LOGGER.info("Getting an OTel baggage entry");
    var value = this.baggage.getEntryValue(args.key());
    return new GetBaggageResult(value);
  }

  @GetMapping("get_all_baggage")
  public GetAllBaggageResult getAllBaggage() {
    LOGGER.info("Getting all OTel baggage entries");
    Map<String, String> baggageMap = new HashMap<>();
    this.baggage.forEach((key, entry) -> baggageMap.put(key, entry.getValue()));
    return new GetAllBaggageResult(baggageMap);
  }

  @PostMapping("remove_baggage")
  public void removeBaggage(@RequestBody RemoveBaggageArgs args) {
    LOGGER.info("Removing OTel baggage entry: {}", args);
    this.baggage = this.baggage
            .toBuilder()
            .remove(args.key())
            .build();
  }

  @PostMapping("remove_all_baggage")
  public void removeAllBaggage() {
    LOGGER.info("Removing all OTel baggage entries");
    this.baggage = Baggage.empty();
  }

  private Span getSpan(long spanId) {
    Span span = this.spans.get(spanId);
    if (span == null) {
      LOGGER.warn("OTel span {} does not exist.", spanId);
    }
    return span;
  }
}
