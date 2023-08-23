package com.datadoghq.system_tests.iast.utils;

import java.io.PrintWriter;

public class XSSExamples {

    public void insecureXSS(final PrintWriter pw, final String param) {
            pw.write(param);
    }

    public void secureXSS(final PrintWriter pw) {
            pw.write("secure");
    }
}
