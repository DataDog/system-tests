package com.datadoghq.system_tests.iast.utils;

import javax.xml.xpath.XPathExpressionException;
import javax.xml.xpath.XPathFactory;
import java.lang.reflect.UndeclaredThrowableException;

public class XPathExamples {

    public void insecureXPath(final String expression) {
        try {
            XPathFactory.newInstance().newXPath().compile(expression);
        } catch (XPathExpressionException e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public void secureXPath() {
        try {
            XPathFactory.newInstance().newXPath().compile("expression");
        } catch (XPathExpressionException e) {
            throw new UndeclaredThrowableException(e);
        }
    }
}
