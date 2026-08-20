package com.datadoghq.system_tests.iast.utils;

import bsh.EvalError;
import bsh.Interpreter;
import java.lang.reflect.UndeclaredThrowableException;

public class CodeInjectionExamples {

    public String insecureCodeInjection(final String code) {
        try {
            new Interpreter().eval(code);
            return "Code injection insecure";
        } catch (EvalError e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public String secureCodeInjection() {
        try {
            new Interpreter().eval("1+2");
            return "Code injection secure";
        } catch (EvalError e) {
            throw new UndeclaredThrowableException(e);
        }
    }
}
