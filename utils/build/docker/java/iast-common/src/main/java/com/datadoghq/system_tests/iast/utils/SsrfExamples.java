package com.datadoghq.system_tests.iast.utils;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class SsrfExamples {

    public String insecureUrl(final String value) {
        try {
            final URL url = new URL(value);
            final HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.disconnect();
        } catch (final Exception e) { }
        return "OK";
    }
}
