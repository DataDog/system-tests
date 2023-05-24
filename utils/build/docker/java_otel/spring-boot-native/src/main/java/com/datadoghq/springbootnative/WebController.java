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
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;
import io.opentelemetry.semconv.trace.attributes.SemanticAttributes;
import org.springframework.http.HttpHeaders;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WebController {
  private final Tracer tracer = GlobalOpenTelemetry.getTracer("com.datadoghq.springbootnative");

  // Home '/' is only used for health check, it generates and sends one span to proxy to indicate interfaces are ready.
  @RequestMapping("/")
  private String home(@RequestHeader HttpHeaders headers) {
    tracer.spanBuilder("Healthcheck").setSpanKind(SpanKind.SERVER).startSpan().end();
    return "Weblog is ready";
  }

  // Basic test scenario that generates a server span with a span link to a fake message span.
  @RequestMapping("/basic/trace")
  private String basic(@RequestHeader HttpHeaders headers) throws InterruptedException {
    try (Scope scope = Context.current().makeCurrent()) {
      SpanContext spanContext = fakeAsyncWork(headers);
      Span span = tracer.spanBuilder("WebController.basic")
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

  @RequestMapping("/container_tagging")
  private String containerTagging(@RequestHeader HttpHeaders headers) throws InterruptedException {
    try (Scope scope = Context.current().makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.container_tagging")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(ResourceAttributes.CONTAINER_ID, "systest-container-id")
              .setAttribute(ResourceAttributes.CONTAINER_NAME, "systest-container")
              .setAttribute(ResourceAttributes.CONTAINER_IMAGE_NAME, "systest-container-image")
              .setAttribute(ResourceAttributes.CONTAINER_IMAGE_TAG, "systest-container-image-tag")
              .setAttribute(ResourceAttributes.K8S_CLUSTER_NAME, "systest-cluster")
              .setAttribute(ResourceAttributes.K8S_NODE_NAME, "systest-node")
              .setAttribute(ResourceAttributes.K8S_POD_NAME, "systest-pod")
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
}
