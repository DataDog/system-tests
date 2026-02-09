package com.datadoghq.springbootnative;

import static datadog.appsec.api.user.User.setUser;

import datadog.appsec.api.login.EventTrackerV2;
import datadog.trace.api.interceptor.MutableSpan;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.aot.hint.annotation.RegisterReflectionForBinding;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import jakarta.servlet.http.HttpServletResponse;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;
import java.util.HashMap;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import static java.util.Collections.emptyMap;

@RestController
public class WebController {

  private static final Logger logger = LoggerFactory.getLogger(App.class);

  @RequestMapping("/")
  String home() {
    return "Hello World!";
  }

  @RequestMapping("/healthcheck")
  Map<String, Object> healtchcheck() {

      String version;
      ClassLoader cl = ClassLoader.getSystemClassLoader();

      try (final BufferedReader reader =
          new BufferedReader(
              new InputStreamReader(
                  cl.getResourceAsStream("dd-java-agent.version"), StandardCharsets.ISO_8859_1))) {
          String line = reader.readLine();
          if (line == null) {
              throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Can't get version");
          }
          version = line;
      } catch (Exception e) {
          throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Can't get version");
      }

      Map<String, String> library = new HashMap<>();
      library.put("name", "java");
      library.put("version", version);

      Map<String, Object> response = new HashMap<>();
      response.put("status", "ok");
      response.put("library", library);

      return response;
  }

  @GetMapping("/headers")
  String headers(HttpServletResponse response) {
    response.setHeader("content-language", "en-US");
    return "012345678901234567890123456789012345678901";
  }

  @RequestMapping("/status")
  ResponseEntity<String> status(@RequestParam Integer code) {
    return new ResponseEntity<>(HttpStatus.valueOf(code));
  }

  @RequestMapping("/stats-unique")
  ResponseEntity<String> statsUnique(@RequestParam(defaultValue = "200") Integer code) {
    return new ResponseEntity<>(HttpStatus.valueOf(code));
  }

  @RequestMapping("/hello")
  public String hello() {
    return "Hello world";
  }

  @RequestMapping("/sample_rate_route/{i}")
  String sample_route(@PathVariable("i") String i) {
    return "OK";
  }

  @RequestMapping("/params/{str}")
  String params_route(@PathVariable("str") String str) {
    return "OK";
  }

  private static final Map<String, String> METADATA = createMetadata();
  private static final Map<String, String> createMetadata() {
    HashMap<String, String> h = new HashMap<>();
    h.put("metadata0", "value0");
    h.put("metadata1", "value1");
    return h;
  }

  @GetMapping("/user_login_success_event")
  public String userLoginSuccess(
          @RequestParam(value = "event_user_id", defaultValue = "system_tests_user") String userId) {
    datadog.trace.api.GlobalTracer.getEventTracker()
            .trackLoginSuccessEvent(userId, METADATA);

    return "ok";
  }

  @GetMapping("/user_login_failure_event")
  public String userLoginFailure(
          @RequestParam(value = "event_user_id", defaultValue = "system_tests_user") String userId,
          @RequestParam(value = "event_user_exists", defaultValue = "true") boolean eventUserExists) {
    datadog.trace.api.GlobalTracer.getEventTracker()
            .trackLoginFailureEvent(userId, eventUserExists, METADATA);

    return "ok";
  }

  @GetMapping("/custom_event")
  public String customEvent(
          @RequestParam(value = "event_name", defaultValue = "system_tests_event") String eventName) {
    datadog.trace.api.GlobalTracer.getEventTracker()
            .trackCustomEvent(eventName, METADATA);

    return "ok";
  }

  @SuppressWarnings("unchecked")
  @PostMapping("/user_login_success_event_v2")
  public String userLoginSuccessV2(@RequestBody final Map<String, Object> body) {
    final String login = body.getOrDefault("login", "system_tests_login").toString();
    final String userId = body.getOrDefault("user_id", "system_tests_user_id").toString();
    final Map<String, String> metadata = (Map<String, String>) body.getOrDefault("metadata", emptyMap());
    EventTrackerV2.trackUserLoginSuccess(login, userId, metadata);
    return "ok";
  }

  @SuppressWarnings("unchecked")
  @PostMapping("/user_login_failure_event_v2")
  public String userLoginFailureV2(@RequestBody final Map<String, Object> body) {
    final String login = body.getOrDefault("login", "system_tests_login").toString();
    final boolean exists = Boolean.parseBoolean(body.getOrDefault("exists", "true").toString());
    final Map<String, String> metadata = (Map<String, String>) body.getOrDefault("metadata", emptyMap());
    EventTrackerV2.trackUserLoginFailure(login, exists, metadata);
    return "ok";
  }

  @GetMapping("/identify")
  public String identify() {
    final Map<String, String> metadata = new HashMap<>();
    metadata.put("email", "usr.email");
    metadata.put("name", "usr.name");
    metadata.put("session_id", "usr.session_id");
    metadata.put("role", "usr.role");
    metadata.put("scope", "usr.scope");
    setUser("usr.id", metadata);
    return "OK";
  }

  @RequestMapping("/make_distant_call")
  DistantCallResponse make_distant_call(@RequestParam String url) throws Exception {
    URL urlObject = new URL(url);

    HttpURLConnection con = (HttpURLConnection) urlObject.openConnection();
    con.setRequestMethod("GET");

    // Save request headers
    HashMap<String, String> request_headers = new HashMap<String, String>();
    for (Map.Entry<String, List<String>> header: con.getRequestProperties().entrySet()) {
      if (header.getKey() == null) {
        continue;
      }

      request_headers.put(header.getKey(), header.getValue().get(0));
    }

    // Save response headers and status code
    int status_code = con.getResponseCode();
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

  @GetMapping("/log/library")
  public String logLibrary(@RequestParam String msg) {
      logger.info(msg);
      return "ok";
  }

  @GetMapping("/endpoint_fallback")
  public ResponseEntity<Map<String, Object>> endpointFallback(
          @RequestParam(name = "case", required = false) String caseParam,
          HttpServletResponse response) {
      Map<String, Object> responseBody = new HashMap<>();
      String testCase = (caseParam != null) ? caseParam : "unknown";

      switch (testCase) {
          case "with_route":
              // Test case: http.route is present - should use it for sampling
              setRootSpanTag("http.route", "/users/{id}/profile");
              setRootSpanTag("http.method", "GET");

              responseBody.put("status", "ok");
              responseBody.put("test_case", "with_route");
              responseBody.put("message", "http.route is set");
              return ResponseEntity.ok(responseBody);

          case "with_endpoint":
              // Test case: http.route is absent, http.endpoint is present - should use http.endpoint for sampling
              // Note: Do NOT set http.route
              setRootSpanTag("http.endpoint", "/api/products/{param:int}");
              setRootSpanTag("http.method", "GET");

              responseBody.put("status", "ok");
              responseBody.put("test_case", "with_endpoint");
              responseBody.put("message", "http.endpoint is set, http.route is not");
              return ResponseEntity.ok(responseBody);

          case "404":
              // Test case: http.route is absent, http.endpoint is present, but status is 404 - should NOT sample
              // Note: Do NOT set http.route
              setRootSpanTag("http.endpoint", "/api/notfound/{param:int}");
              setRootSpanTag("http.method", "GET");

              responseBody.put("status", "error");
              responseBody.put("test_case", "404_with_endpoint");
              responseBody.put("message", "Not found - should not sample despite http.endpoint");
              return ResponseEntity.status(HttpStatus.NOT_FOUND).body(responseBody);

          case "computed":
              // Test case: Neither http.route nor http.endpoint set - should compute endpoint on-demand
              // The endpoint should be computed but NOT added as a tag on the span
              // Note: Do NOT set http.route or http.endpoint
              // Set http.url so endpoint can be computed
              setRootSpanTag("http.url", "http://localhost:8080/endpoint_fallback_computed/users/123/orders/456");
              setRootSpanTag("http.method", "GET");

              responseBody.put("status", "ok");
              responseBody.put("test_case", "computed_on_demand");
              responseBody.put("message", "Endpoint computed from URL");
              return ResponseEntity.ok(responseBody);

          default:
              responseBody.put("status", "error");
              responseBody.put("test_case", "unknown");
              responseBody.put("message", "Invalid case parameter. Valid values: with_route, with_endpoint, 404, computed");
              return ResponseEntity.badRequest().body(responseBody);
      }
  }

  private void setRootSpanTag(final String key, final String value) {
      final Span span = GlobalTracer.get().activeSpan();
      if (span instanceof MutableSpan) {
          final MutableSpan rootSpan = ((MutableSpan) span).getLocalRootSpan();
          if (rootSpan != null) {
              rootSpan.setTag(key, value);
          }
      }
  }

  public static final class DistantCallResponse {
    public String url;
    public int status_code;
    public HashMap<String, String> request_headers;
    public HashMap<String, String> response_headers;
  }

  @RegisterReflectionForBinding({ShellExecutionRequest.class, ShellExecutionRequest.Options.class})
  @PostMapping(value = "/shell_execution", consumes = MediaType.APPLICATION_JSON_VALUE)
  String shellExecution(@RequestBody final ShellExecutionRequest request) throws IOException, InterruptedException {
    Process p;
    if (request.options.shell) {
      throw new RuntimeException("Not implemented");
    } else {
      final String[] args = request.args.split("\\s+");
      final String[] command = new String[args.length + 1];
      command[0] = request.command;
      System.arraycopy(args, 0, command, 1, args.length);
      p = new ProcessBuilder(command).start();
    }
    p.waitFor(10, TimeUnit.SECONDS);
    final int exitCode = p.exitValue();
    return "OK: " + exitCode;
  }

  private static class ShellExecutionRequest {
    public String command;
    public String args;
    public Options options;

    static class Options {
      public boolean shell;
    }
  }
}
