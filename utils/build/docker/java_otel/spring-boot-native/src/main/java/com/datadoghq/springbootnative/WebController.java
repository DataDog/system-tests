package com.datadoghq.springbootnative;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapPropagator;
import io.opentelemetry.semconv.trace.attributes.SemanticAttributes;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WebController {
  private final Tracer tracer = GlobalOpenTelemetry.getTracer("com.datadoghq.springbootnative");
  private final TextMapPropagator propagator = GlobalOpenTelemetry.getPropagators().getTextMapPropagator();

  private static final TextMapGetter<HttpHeaders> getter =
    new TextMapGetter<>() {
      @Override
      public String get(HttpHeaders headers, String key) {
        List<String> vals = headers.get(key);
        return vals == null ? "" : vals.get(0);
      }

      @Override
      public Iterable<String> keys(HttpHeaders headers) {
        return headers.keySet();
      }
    };

  @RequestMapping("/")
  String home(@RequestHeader HttpHeaders headers) throws InterruptedException {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      // Create a fake producer span to test span links
      Span fakeSpan = tracer.spanBuilder("WebController.home.publish")
              .setSpanKind(SpanKind.PRODUCER)
              .setAttribute("messaging.system", "rabbitmq")
              .setAttribute("messaging.operation", "publish")
              .startSpan();
      Thread.sleep(1);
      fakeSpan.end();

      Span span = tracer.spanBuilder("WebController.home")
              .setSpanKind(SpanKind.SERVER)
              .addLink(
                      fakeSpan.getSpanContext(),
                      Attributes.of(AttributeKey.stringKey("messaging.operation"), "publish"))
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/")
              .setAttribute(SemanticAttributes.HTTP_METHOD, "GET")
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        Thread.sleep(5);
        return "Hello World!";
      } finally {
        span.end();
      }
    }
  }

  @GetMapping("/headers")
  String headers(HttpServletResponse response, @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.headers")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/headers")
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        response.setHeader("content-language", "en-US");
        return "012345678901234567890123456789012345678901";
      }
      finally {
        span.end();
      }
    }
  }

  @RequestMapping("/status")
  ResponseEntity<String> status(@RequestParam Integer code, @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.status")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/status")
              .setAttribute(SemanticAttributes.HTTP_STATUS_CODE, code == null ? 0 : code.longValue())
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        return new ResponseEntity<>(HttpStatus.valueOf(code));
      }
      finally {
        span.end();
      }
    }
  }

  @RequestMapping("/hello")
  public String hello(@RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.hello")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/hello")
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        return "Hello world";
      }
      finally {
        span.end();
      }
    }
  }

  @RequestMapping("/sample_rate_route/{i}")
  String sample_route(@PathVariable("i") String i, @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.sample_route")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/sample_rate_route/{i}")
              .setAttribute("i", i)
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        return "OK";
      }
      finally {
        span.end();
      }
    }
  }

  @RequestMapping("/params/{str}")
  String params_route(@PathVariable("str") String str, @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.params_route")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/params/{str}")
              .setAttribute("str", str)
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        return "OK";
      }
      finally {
        span.end();
      }
    }
  }

  @GetMapping("/user_login_success_event")
  public String userLoginSuccess(
          @RequestParam(value = "event_user_id", defaultValue = "system_tests_user") String userId, 
          @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.userLoginSuccess")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/user_login_success_event")
              .setAttribute("event_user_id", userId)
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        return "OK";
      }
      finally {
        span.end();
      }
    }
  }

  @GetMapping("/user_login_failure_event")
  public String userLoginFailure(
          @RequestParam(value = "event_user_id", defaultValue = "system_tests_user") String userId,
          @RequestParam(value = "event_user_exists", defaultValue = "true") boolean eventUserExists,
          @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.userLoginFailure")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/user_login_failure_event")
              .setAttribute("event_user_id", userId)
              .setAttribute("event_user_exists", eventUserExists)
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        return "OK";
      }
      finally {
        span.end();
      }
    }
  }

  @GetMapping("/custom_event")
  public String customEvent(
          @RequestParam(value = "event_name", defaultValue = "system_tests_event") String eventName,
          @RequestHeader HttpHeaders headers) {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.customEvent")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/custom_event")
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        span.addEvent("custom_event", Attributes.of(AttributeKey.stringKey("event_name"), eventName));
        return "OK";
      }
      finally {
        span.end();
      }
    }
  }

  @RequestMapping("/make_distant_call")
  DistantCallResponse make_distant_call(
    @RequestParam String url, @RequestHeader HttpHeaders headers) throws Exception {
    try (Scope scope = propagator.extract(Context.current(), headers, getter).makeCurrent()) {
      Span span = tracer.spanBuilder("WebController.make_distant_call")
              .setSpanKind(SpanKind.SERVER)
              .setAttribute(SemanticAttributes.HTTP_ROUTE, "/make_distant_call")
              .setAttribute(SemanticAttributes.HTTP_URL, url)
              .startSpan();
      try (Scope ignored = span.makeCurrent()) {
        URL urlObject = new URL(url);

        HttpURLConnection con = (HttpURLConnection) urlObject.openConnection();
        con.setRequestMethod("GET");

        Span child = tracer.spanBuilder("WebController.make_distant_call.get")
                .setSpanKind(SpanKind.CLIENT)
                .setAttribute(SemanticAttributes.HTTP_URL, url)
                .setAttribute(SemanticAttributes.HTTP_METHOD, "GET")
                .startSpan();

        // Save request headers
        HashMap<String, String> request_headers = new HashMap<String, String>();
        for (Map.Entry<String, List<String>> header: con.getRequestProperties().entrySet()) {
          if (header.getKey() == null) {
            continue;
          }

          request_headers.put(header.getKey(), header.getValue().get(0));
          child.setAttribute(header.getKey(), header.getValue().get(0));
        }

        // Save response headers and status code
        int status_code = con.getResponseCode();
        child.setAttribute(SemanticAttributes.HTTP_STATUS_CODE, status_code);
        child.end();

        HashMap<String, String> response_headers = new HashMap<String, String>();
        for (Map.Entry<String, List<String>> header: con.getHeaderFields().entrySet()) {
          if (header.getKey() == null) {
            continue;
          }

          response_headers.put(header.getKey(), header.getValue().get(0));
        }

        DistantCallResponse result = new DistantCallResponse();
        result.url = url;
        result.status_code = status_code;
        result.request_headers = request_headers;
        result.response_headers = response_headers;

        return result;
      }
      finally {
        span.end();
      }
    }
  }

  public static final class DistantCallResponse {
    public String url;
    public int status_code;
    public HashMap<String, String> request_headers;
    public HashMap<String, String> response_headers;
  }
}
