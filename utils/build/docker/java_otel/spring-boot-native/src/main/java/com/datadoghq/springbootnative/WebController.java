package com.datadoghq.springbootnative;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.logs.GlobalLoggerProvider;
import io.opentelemetry.api.logs.Logger;
import io.opentelemetry.api.logs.Severity;
import io.opentelemetry.api.metrics.DoubleHistogram;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.metrics.ObservableDoubleMeasurement;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.semconv.trace.attributes.SemanticAttributes;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.HashMap;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.io.IOException;

@RestController
public class WebController {
  private final Tracer tracer = GlobalOpenTelemetry.getTracer("com.datadoghq.springbootnative");
  private final Meter meter = GlobalOpenTelemetry.getMeter("com.datadoghq.springbootnative");
  private final LongCounter counter = meter.counterBuilder("example.counter").build();
  private final DoubleHistogram histogram = meter.histogramBuilder("example.histogram").build();
  private final Logger customAppenderLogger = GlobalLoggerProvider.get().get("com.datadoghq.springbootnative");

  @RequestMapping("/")
  private String home(@RequestHeader HttpHeaders headers) {
    return "Weblog is ready";
  }

  @RequestMapping("/healthcheck")
  Map<String, Object> healtchcheck() {
      tracer.spanBuilder("Healthcheck").setSpanKind(SpanKind.SERVER).startSpan().end();

      String filePath = "/app/SYSTEM_TESTS_LIBRARY_VERSION";
      String version;
      try {
          version = new String(Files.readAllBytes(Paths.get(filePath)));
      } catch (IOException e) {
          throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Can't get version");
      }

      Map<String, String> library = new HashMap<>();
      library.put("name", "java_otel");
      library.put("version", version.strip());

      Map<String, Object> response = new HashMap<>();
      response.put("status", "ok");
      response.put("library", library);

      return response;
  }

  // Basic trace test scenario that generates a server span with a span link to a fake message span.
  @RequestMapping("/basic/trace")
  private String basicTrace(@RequestHeader HttpHeaders headers) throws InterruptedException {
    try (Scope scope = Context.current().makeCurrent()) {
      SpanContext spanContext = fakeAsyncWork(headers);
      Span span = tracer.spanBuilder("WebController.basic")
              .setSpanKind(SpanKind.SERVER)
              .addLink(spanContext, Attributes.of(AttributeKey.stringKey("messaging.operation"), "publish"))
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/")
              .setAttribute(SemanticAttributes.HTTP_METHOD, "GET")
              .setAttribute(AttributeKey.booleanKey("bool_key"), false)
              .setAttribute("http.request.headers.user-agent", headers.get("User-Agent").get(0))
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        Thread.sleep(5);
        return "Hello World!";
      } finally {
        span.end();
      }
    }
  }

  // Create a fake producer span and return its span context to test span links
  private SpanContext fakeAsyncWork(HttpHeaders headers) throws InterruptedException {
    Span fakeSpan = tracer.spanBuilder("WebController.basic.publish")
            .setSpanKind(SpanKind.PRODUCER)
            .setAttribute("messaging.system", "rabbitmq")
            .setAttribute("messaging.operation", "publish")
            .setAttribute("http.request.headers.user-agent", headers.get("User-Agent").get(0))
            .startSpan();
    Thread.sleep(1);
    fakeSpan.end();
    return fakeSpan.getSpanContext();
  }

  // Basic metric test scenario that increments the example counter and histogram.
  @RequestMapping("/basic/metric")
  private String basicMetric(@RequestHeader HttpHeaders headers) throws InterruptedException {
    String userAgent = headers.get("User-Agent").get(0);
    String rid = userAgent.substring("system_tests rid/".length(), userAgent.length());
    counter.add(11L,
            Attributes.of(SemanticAttributes.HTTP_METHOD, "GET", AttributeKey.stringKey("rid"), rid));
    histogram.record(33L,
            Attributes.of(SemanticAttributes.HTTP_METHOD, "GET", AttributeKey.stringKey("rid"), rid));
    Thread.sleep(2000);
    return "Hello World!";
  }

  // Basic log test scenario that generates an OTLP log with trace correlation.
  @RequestMapping("/basic/log")
  private String basicLog(@RequestHeader HttpHeaders headers) throws InterruptedException {
    String userAgent = headers.get("User-Agent").get(0);
    Span span = tracer.spanBuilder("WebController.basic.log")
            .setSpanKind(SpanKind.SERVER)
            .setAttribute(SemanticAttributes.HTTP_ROUTE, "/basic/log")
            .setAttribute(SemanticAttributes.HTTP_METHOD, "GET")
            .setAttribute("http.request.headers.user-agent", userAgent)
            .startSpan();
    try (Scope ignored = span.makeCurrent()) {
      customAppenderLogger
              .logRecordBuilder()
              .setSeverity(Severity.INFO)
              .setBody("Handle request with user agent: " + userAgent)
              .setAttribute(SemanticAttributes.HTTP_METHOD, "GET")
              .setAttribute(AttributeKey.stringKey("http.request.headers.user-agent"), userAgent)
              .emit();
    } finally {
      span.end();
    }
    Thread.sleep(2000);
    return "Hello World!";
  }
}
