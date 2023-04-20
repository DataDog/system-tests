package com.datadoghq.system_tests.iast.infra;

public interface Server<T> {

    T start();

    /**
     * Close the server
     */
    void close();
}
