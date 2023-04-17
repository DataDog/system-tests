package com.datadoghq.springbootnative;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.semconv.trace.attributes.SemanticAttributes;
import org.springframework.http.HttpHeaders;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WebController {
  private final Tracer tracer = GlobalOpenTelemetry.getTracer("com.datadoghq.springbootnative");

  @RequestMapping("/")
  private String home(@RequestHeader HttpHeaders headers) throws InterruptedException {
    try (Scope scope = Context.current().makeCurrent()) {
      SpanContext spanContext = fakeAsyncWork(headers);
      Span span = tracer.spanBuilder("WebController.home")
              .setSpanKind(SpanKind.SERVER)
              .addLink(spanContext, Attributes.of(AttributeKey.stringKey("messaging.operation"), "publish"))
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/")
              .setAttribute(SemanticAttributes.HTTP_METHOD, "GET")
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
    Span fakeSpan = tracer.spanBuilder("WebController.home.publish")
            .setSpanKind(SpanKind.PRODUCER)
            .setAttribute("messaging.system", "rabbitmq")
            .setAttribute("messaging.operation", "publish")
            .setAttribute("http.request.headers.user-agent", headers.get("User-Agent").get(0))
            .startSpan();
    Thread.sleep(1);
    fakeSpan.end();
    return fakeSpan.getSpanContext();
  }
}
