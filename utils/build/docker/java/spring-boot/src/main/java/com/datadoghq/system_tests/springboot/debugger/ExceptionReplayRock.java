package com.datadoghq.system_tests.springboot.debugger;

public class ExceptionReplayRock extends Exception {
    public ExceptionReplayRock() {
        super("Rock exception");
    }
}
