package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Routes for the RFC-1125 normalized route tests (tests/appsec/api_security_testing/test_normalized_route.py).
 * Only the declared patterns matter: the handlers do not read the path variables.
 */
@RestController
@RequestMapping("/api_security")
public class NormalizedRouteController {

  private static final String OK = "ok";

  @GetMapping("/multi-params-in-segment/{id}.{format}")
  public String multiParamsInSegment() {
    return OK;
  }

  @GetMapping("/three-params/{a}-{b}-{c}")
  public String threeParams() {
    return OK;
  }

  // the regex keeps `123.json` for the route with a format: Spring prefers the route with fewer
  // variables, and the tracer drops the regex from the tag
  @GetMapping({"/optional-params/{id:[^.]+}", "/optional-params/{id}.{format}"})
  public String optionalParams() {
    return OK;
  }

  @GetMapping("/static-text/user-{id}")
  public String staticText() {
    return OK;
  }

  @GetMapping("/version/v{version}/items")
  public String staticTextBeforeParam() {
    return OK;
  }

  @GetMapping("/files/{name}.json")
  public String staticTextAfterParam() {
    return OK;
  }

  @GetMapping({"/optional-segment/{id}", "/optional-segment/{id}/{tab}"})
  public String optionalSegment() {
    return OK;
  }

  @GetMapping({"/search", "/search.{format}"})
  public String search() {
    return OK;
  }

  @GetMapping({"/optional-chain", "/optional-chain/{x}", "/optional-chain/{x}/{y}"})
  public String optionalChain() {
    return OK;
  }

  @GetMapping("/catch-all/{*path}")
  public String catchAll() {
    return OK;
  }

  @GetMapping("/encoded/caf\u00e9")
  public String encoded() {
    return OK;
  }

  @GetMapping("/param-names/{user-id}/{user_id}")
  public String paramNames() {
    return OK;
  }

  @GetMapping({"/drafts", "/drafts/preview"})
  public String drafts() {
    return OK;
  }
}
