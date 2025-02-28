package com.datadoghq.springbootnative;

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
      library.put("language", "java");
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
      // final Span span = GlobalTracer.get().activeSpan();
      // logger.info("testing: " + span.context().toTraceId());
      logger.info("matt li test");
      logger.info(msg);
      return "ok";
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
