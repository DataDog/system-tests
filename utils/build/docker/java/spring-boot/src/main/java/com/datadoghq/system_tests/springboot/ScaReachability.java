package com.datadoghq.system_tests.springboot;

import javax.annotation.PostConstruct;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.yaml.snakeyaml.Yaml;

@RestController
@RequestMapping("/sca")
public class ScaReachability {

  @PostConstruct
  private void preloadVulnerableClass() {
    // Force Yaml class load during Spring startup so the SCA transformer can register the CVE
    // with reached=[] before any HTTP request triggers yaml.load(). Without this, the class
    // loads lazily on the first /sca/vulnerable-call request, causing registerCve() and
    // recordHit() to fire in the same request with no heartbeat window between them.
    new Yaml();
  }

  @GetMapping("/vulnerable-call")
  public String scaVulnerableCall() {
    Yaml yaml = new Yaml();
    yaml.load("key: value");
    return "OK";
  }

  @GetMapping("/vulnerable-call-alt")
  public String scaVulnerableCallAlt() {
    Yaml yaml = new Yaml();
    yaml.load("alt: value");
    return "OK";
  }
}
