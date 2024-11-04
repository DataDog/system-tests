package com.datadoghq.system_tests.springboot;

public class ExceptionReplayScissors extends Exception {
    public ExceptionReplayScissors() {
        super("Scissors exception");
    }
}
