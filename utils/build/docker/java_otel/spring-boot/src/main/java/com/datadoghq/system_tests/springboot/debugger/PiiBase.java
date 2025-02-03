package com.datadoghq.system_tests.springboot;

public abstract class PiiBase {
    public static final String VALUE = "SHOULD_BE_REDACTED";
    public String TestValue = VALUE;
}