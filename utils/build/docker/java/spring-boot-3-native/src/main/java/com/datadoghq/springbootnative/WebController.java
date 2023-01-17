package com.datadoghq.springbootnative;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletResponse;

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
}