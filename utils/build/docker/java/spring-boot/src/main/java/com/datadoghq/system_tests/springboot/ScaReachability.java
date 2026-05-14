package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.yaml.snakeyaml.Yaml;

@RestController
@RequestMapping("/sca")
public class ScaReachability {

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
