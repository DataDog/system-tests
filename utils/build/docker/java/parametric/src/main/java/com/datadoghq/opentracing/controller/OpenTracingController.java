package com.datadoghq.opentracing.controller;

import static com.datadoghq.ApmTestClient.LOGGER;
import static datadog.trace.api.DDTags.ORIGIN_KEY;
import static datadog.trace.api.DDTags.RESOURCE_NAME;
import static datadog.trace.api.DDTags.SERVICE_NAME;
import static datadog.trace.api.DDTags.SPAN_TYPE;
import static io.opentracing.propagation.Format.Builtin.TEXT_MAP;

import com.datadoghq.opentracing.dto.SpanErrorArgs;
import com.datadoghq.opentracing.dto.SpanFinishArgs;
import com.datadoghq.opentracing.dto.SpanInjectHeadersArgs;
import com.datadoghq.opentracing.dto.SpanInjectHeadersResult;
import com.datadoghq.opentracing.dto.SpanSetMetaArgs;
import com.datadoghq.opentracing.dto.SpanSetMetricArgs;
import com.datadoghq.opentracing.dto.StartSpanArgs;
import com.datadoghq.opentracing.dto.StartSpanResult;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTags;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.internal.InternalTracer;
import io.opentracing.Span;
import io.opentracing.SpanContext;
import io.opentracing.Tracer;
import io.opentracing.Tracer.SpanBuilder;
import io.opentracing.propagation.TextMapAdapter;
import io.opentracing.tag.Tags;
import io.opentracing.util.GlobalTracer;
import jakarta.annotation.PreDestroy;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.io.Closeable;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping(value = "/trace/span", consumes = "application/json", produces = "application/json")
public class OpenTracingController implements Closeable {
  private final Tracer tracer;
  private final Map<Long, Span> spans;

  public OpenTracingController() {
    this.tracer = GlobalTracer.get();
    this.spans = new HashMap<>();
  }

  @PostMapping("start")
  public StartSpanResult startSpan(@RequestBody StartSpanArgs args) {
    LOGGER.info("Starting OT span: {}", args);
    try {
      // Build span from request
      SpanBuilder builder = this.tracer.buildSpan(args.name())
          .withTag(SERVICE_NAME, args.service())
          .withTag(RESOURCE_NAME, args.resource())
          .withTag(SPAN_TYPE, args.type())
          .withTag(ORIGIN_KEY, args.origin());
      // The parent id can be negative since we have a long representing uint64
      if (args.parentId() != 0) {
        Span parentSpan = getSpan(args.parentId());
        if (parentSpan == null) {
          return StartSpanResult.error();
        }
        builder.asChildOf(parentSpan);
      }
      // Extract propagation headers from args to use them as parent context
      if (args.headers() != null) {
        SpanContext context = this.tracer.extract(TEXT_MAP, new TextMapAdapter(args.headers()));
        builder.asChildOf(context);
      }
      // Links are not supported as we choose to not support them through OpenTracing API
      if (args.links() != null && !args.links().isEmpty()) {
        LOGGER.warn("Span links are unsupported using the OpenTracing API");
      }
      Span span = builder.start();
      // Store span
      long spanId = DDSpanId.from(span.context().toSpanId());
      long traceId = DDTraceId.from(span.context().toTraceId()).toLong();
      this.spans.put(spanId, span);
      // Complete request
      return new StartSpanResult(traceId, spanId);
    } catch (Throwable t) {
      LOGGER.error("Uncaught throwable", t);
      return StartSpanResult.error();
    }
  }

  @PostMapping("finish")
  public void finishSpan(@RequestBody SpanFinishArgs args) {
    LOGGER.info("Finishing OT span: {}", args);
    Span span = getSpan(args.spanId());
    if (span != null) {
      span.finish();
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
    Map<String, String> headers = new HashMap<>();
    Span span = getSpan(args.spanId());
    if (span != null) {
      // Get context from span and inject it to carrier
      TextMapAdapter carrier = new TextMapAdapter(headers);
      this.tracer.inject(span.context(), TEXT_MAP, carrier);
    }
    return new SpanInjectHeadersResult(headers);
  }

  @PostMapping("flush")
  public void flushSpans() {
    LOGGER.info("Flushing OT spans");
    try {
      ((InternalTracer) this.tracer).flush();
      this.spans.clear();
    } catch (Throwable t) {
      LOGGER.error("Uncaught throwable", t);
    }
  }

  private Span getSpan(long spanId) {
    Span span = this.spans.get(spanId);
    if (span == null) {
      LOGGER.warn("OT span {} does not exist.", spanId);
    }
    return span;
  }

  @PreDestroy
  public void close() {
    LOGGER.info("Closing OT tracer");
    this.tracer.close();
  }
}
