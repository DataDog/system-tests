package com.datadoghq.system_tests.springboot.iast.utils;

import javax.xml.bind.annotation.XmlRootElement;

@XmlRootElement(name = "TestBean")
public class TestBean {

  private String name;
  private String value;

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public String getValue() {
    return value;
  }

  public void setValue(String value) {
    this.value = value;
  }
}
