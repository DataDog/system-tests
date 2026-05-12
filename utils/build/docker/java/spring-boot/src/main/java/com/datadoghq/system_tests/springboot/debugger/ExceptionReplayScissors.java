package com.datadoghq.system_tests.springboot.debugger;

public class ExceptionReplayScissors extends Exception {
    public ExceptionReplayScissors() {
        super("Scissors exception");
    }
}
