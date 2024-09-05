package com.datadoghq.system_tests.iast.utils;

public class ReflectionExamples {

    public String secureClassForName() {
        try {
            Class.forName("java.lang.String");
        } catch (ClassNotFoundException e) {
            // ignore it
        }
        return "Secure";
    }

    public String insecureClassForName(final String value) {
        try {
            Class.forName(value);
        } catch (ClassNotFoundException e) {
            // ignore it
        }
        return "Insecure";
    }
}
