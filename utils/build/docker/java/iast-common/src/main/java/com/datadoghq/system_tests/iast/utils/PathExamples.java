package com.datadoghq.system_tests.iast.utils;

import java.nio.file.Paths;

public class PathExamples {

    public String insecurePathTraversal(final String path) {
        return Paths.get(path).toString();
    }
}
