package com.datadoghq.trace.opentracing.controller;

import static com.datadoghq.ApmTestClient.LOGGER;
import static datadog.trace.api.DDTags.RESOURCE_NAME;
import static datadog.trace.api.DDTags.SERVICE_NAME;
import static datadog.trace.api.DDTags.SPAN_TYPE;
import static io.opentracing.propagation.Format.Builtin.TEXT_MAP;
import static java.util.Collections.emptyList;
import static java.util.stream.Collectors.toCollection;

import com.datadoghq.trace.opentracing.dto.*;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTags;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.internal.InternalTracer;
import io.opentracing.Span;
import io.opentracing.SpanContext;
import io.opentracing.Tracer;
import io.opentracing.Tracer.SpanBuilder;
import io.opentracing.propagation.TextMap;
import io.opentracing.tag.Tags;
import io.opentracing.util.GlobalTracer;
import jakarta.annotation.PreDestroy;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.io.Closeable;
import java.util.AbstractMap.SimpleEntry;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping(value = "/trace/span")
public class OpenTracingController implements Closeable {
  private final Tracer tracer;
  /** Created spans, indexed by their identifiers .*/
  private final Map<Long, Span> spans;
  /** The extracted span contexts, indexed by span identifier. */
  private final Map<Long, SpanContext> extractedSpanContexts;

  public OpenTracingController() {
    this.tracer = GlobalTracer.get();
    this.spans = new HashMap<>();
    this.extractedSpanContexts = new HashMap<>();
  }

  @PostMapping("start")
  public StartSpanResult startSpan(@RequestBody StartSpanArgs args) {
    LOGGER.info("Starting OT span: {}", args);
    try {
      // Build span from request
      SpanBuilder builder = this.tracer.buildSpan(args.name())
          .withTag(SERVICE_NAME, args.service())
          .withTag(RESOURCE_NAME, args.resource())
          .withTag(SPAN_TYPE, args.type());
      // The parent id can be negative since we have a long representing uint64
      Long parentId = args.parentId();
      if (parentId != null) {
        Span span;
        SpanContext context;
        if ((span = getSpan(parentId)) != null) {
          builder.asChildOf(span);
        } else if ((context = getSpanContext(parentId)) != null) {
          builder.asChildOf(context);
        } else {
          return StartSpanResult.error();
        }
      }
      // Apply tags
      if (args.tags() != null && !args.tags().isEmpty()) {
        args.tags().forEach(tag -> builder.withTag(tag.key(), tag.value()));
      }
      Span span = builder.start();
      // Store span
      long spanId = DDSpanId.from(span.context().toSpanId());
      long traceId = DDTraceId.from(span.context().toTraceId()).toLong();
      this.spans.put(spanId, span);
      // Complete request
      return new StartSpanResult(spanId, traceId);
    } catch (Throwable t) {
      LOGGER.error("Uncaught throwable", t);
      return StartSpanResult.error();
    }
  }

  @GetMapping("current")
  public StartSpanResult currentSpan() {
    Span span = this.tracer.activeSpan();
    if (span == null) {
      return StartSpanResult.error();
    }
    long spanId = DDSpanId.from(span.context().toSpanId());
    long traceId = DDTraceId.from(span.context().toTraceId()).toLong();
    return new StartSpanResult(spanId, traceId);
  }

  @PostMapping("finish")
  public void finishSpan(@RequestBody SpanFinishArgs args) {
    LOGGER.info("Finishing OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.finish();
    }
  }

  @PostMapping("set_resource")
  public void setResource(@RequestBody SpanSetResourceArgs args) {
    LOGGER.info("Setting resource for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null && args.resource() != null) {
      span.setTag(RESOURCE_NAME, args.resource());
    }
  }

  @PostMapping("set_meta")
  public void setMeta(@RequestBody SpanSetMetaArgs args) {
    LOGGER.info("Setting meta for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null && args.key() != null) {
      span.setTag(args.key(), args.value());
    }
  }

  @PostMapping("set_metric")
  public void setMetric(@RequestBody SpanSetMetricArgs args) {
    LOGGER.info("Setting OT span metric: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null && args.key() != null) {
      span.setTag(args.key(), args.value());
    }
  }

  @PostMapping("error")
  public void setError(@RequestBody SpanErrorArgs args) {
    LOGGER.info("Setting OT span error: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.setTag(Tags.ERROR, true);
      span.setTag(DDTags.ERROR_TYPE, args.type());
      span.setTag(DDTags.ERROR_MSG, args.message());
      span.setTag(DDTags.ERROR_STACK, args.stack());
    }
  }

  @PostMapping("inject_headers")
  public SpanInjectHeadersResult injectHeaders(@RequestBody SpanInjectHeadersArgs args) {
    LOGGER.info("Inject headers context to OT tracer: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      // Get context from span and inject it to carrier
      TextMapAdapter carrier = TextMapAdapter.empty();
      this.tracer.inject(span.context(), TEXT_MAP, carrier);
      return new SpanInjectHeadersResult(carrier.toHeaders());
    }
    return new SpanInjectHeadersResult(emptyList());
  }

  @PostMapping("extract_headers")
  public SpanExtractHeadersResult extractHeaders(@RequestBody SpanExtractHeadersArgs args) {
    LOGGER.info("Extract headers context to OT tracer: {}", args);
    SpanContext context = this.tracer.extract(TEXT_MAP, TextMapAdapter.fromRequest(args.headers()));
    if (context == null || context.toSpanId().isEmpty()) {
      return SpanExtractHeadersResult.error();
    }
    long spanId = DDSpanId.from(context.toSpanId());
    this.extractedSpanContexts.put(spanId, context);
    return new SpanExtractHeadersResult(spanId);
  }

  @PostMapping("flush")
  public void flushSpans() {
    LOGGER.info("Flushing OT spans");
    try {
      // Only flush spans when tracing was enabled
      if (datadog.trace.api.GlobalTracer.get() instanceof InternalTracer internalTracer) {
          internalTracer.flush();
      }
      this.spans.clear();
      this.extractedSpanContexts.clear();
    } catch (Throwable t) {
      LOGGER.error("Uncaught throwable", t);
    }
  }

  @PostMapping("set_baggage")
  public void setBaggage(@RequestBody SpanSetBaggageArgs args) {
    LOGGER.info("Setting baggage item for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null && args.key() != null) {
      span.setBaggageItem(args.key(), args.value());
    }
  }

  @GetMapping("get_baggage")
  public SpanGetBaggageResult getBaggage(@RequestBody SpanGetBaggageArgs args) {
    LOGGER.info("Getting single baggage item for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null && args.key() != null) {
      return new SpanGetBaggageResult(span.getBaggageItem(args.key()));
    }
    return null;
  }

  @GetMapping("get_all_baggage")
  public SpanGetAllBaggageResult getAllBaggage(@RequestBody SpanGetAllBaggageArgs args) {
    LOGGER.info("Getting all baggage items for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      Map<String, String> baggageMap = new HashMap<>();

      for (var entry : span.context().baggageItems()) {
        baggageMap.put(entry.getKey(), entry.getValue());
      }

      return new SpanGetAllBaggageResult(baggageMap);
    }
    return null;
  }

  @PostMapping("remove_baggage")
  public void removeBaggage(@RequestBody SpanRemoveBaggageArgs args) {
    LOGGER.info("Removing single baggage item for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null && args.key() != null) {
      span.setBaggageItem(args.key(), null);
    }
  }

  @PostMapping("remove_all_baggage")
  public void removeAllBaggage(@RequestBody SpanRemoveAllBaggageArgs args) {
    LOGGER.info("Removing all baggage items for OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      for (var entry : span.context().baggageItems()) {
        span.setBaggageItem(entry.getKey(), null);
      }
    }
  }

  private Span getSpan(long spanId) {
    Span span = this.spans.get(spanId);
    if (span == null) {
      LOGGER.warn("OT span {} does not exist.", spanId);
    }
    return span;
  }

  private SpanContext getSpanContext(long spanId) {
    SpanContext context = this.extractedSpanContexts.get(spanId);
    if (context == null) {
      LOGGER.warn("OT span context from span identifier {} does not exist.", spanId);
    }
    return context;
  }

  @PreDestroy
  public void close() {
    LOGGER.info("Closing OT tracer");
    this.tracer.close();
  }

  // Don't use Map to allow duplicate entries with the same key
  private record TextMapAdapter(List<Map.Entry<String, String>> entries) implements TextMap {
    private static TextMapAdapter empty() {
      return new TextMapAdapter(new ArrayList<>());
    }

    private static TextMapAdapter fromRequest(List<KeyValue> headers) {
      return new TextMapAdapter(headers.stream()
          .map(kv -> new SimpleEntry<>(kv.key(), kv.value()))
          .collect(toCollection(ArrayList::new)));
    }

    @Override
    public Iterator<Map.Entry<String, String>> iterator() {
      return this.entries.iterator();
    }

    @Override
    public void put(String key, String value) {
      this.entries.add(new SimpleEntry<>(key, value));
    }

    private List<KeyValue> toHeaders() {
      return this.entries.stream()
          .map(entry -> new KeyValue(entry.getKey(), entry.getValue()))
          .toList();
    }
  }
}
