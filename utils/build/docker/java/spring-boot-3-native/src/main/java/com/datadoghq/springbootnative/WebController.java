package com.datadoghq.springbootnative;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletResponse;
import java.util.HashMap;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.List;

@RestController
public class WebController {
  @RequestMapping("/")
  String home() {
    return "Hello World!";
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

  public static final class DistantCallResponse {
    public String url;
    public int status_code;
    public HashMap<String, String> request_headers;
    public HashMap<String, String> response_headers;
  }
}
