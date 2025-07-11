package com.datadoghq.system_tests.iast.utils;

public class SecurityControlUtil {

  public static String sanitize(String input) {
    return "Sanitized " + input;
  }

  public static String sanitizeForAllVulns(String input) {
    return "Sanitized for all vulns " + input;
  }

  public static String overloadedSanitize(String input)  {
    return "Sanitized " + input;
  }

  public static String overloadedSanitize(String input, Object o) {
    return "Sanitized " + input;
  }

  public static boolean validate(String input) {
    return true; // dummy implementation
  }

  public static boolean validateForAllVulns(String input) {
    return true; // dummy implementation
  }

  public static boolean overloadedValidation(String input, String input2) {
    return true; // dummy implementation
  }

  public static boolean overloadedValidation(Object o, String input, String input2) {
    return true; // dummy implementation
  }

}
