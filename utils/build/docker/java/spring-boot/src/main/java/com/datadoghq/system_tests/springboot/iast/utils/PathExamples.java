package com.datadoghq.system_tests.springboot.iast.utils;

import org.springframework.stereotype.Component;

import java.nio.file.Paths;

@Component
public class PathExamples {

    public String insecurePathTraversal(final String path) {
        return Paths.get(path).toString();
    }
}
