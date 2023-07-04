package com.datadoghq.system_tests.iast.utils;

import javax.xml.xpath.XPathExpressionException;
import javax.xml.xpath.XPathFactory;
import java.lang.reflect.UndeclaredThrowableException;

public class XPathExamples {

    public String insecureXPath(final String expression) {
        try {
            XPathFactory.newInstance().newXPath().compile(expression);
            return "XPath insecure";
        } catch (XPathExpressionException e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public String secureXPath() {
        try {
            XPathFactory.newInstance().newXPath().compile("expression");
            return "XPath secure";
        } catch (XPathExpressionException e) {
            throw new UndeclaredThrowableException(e);
        }
    }
}
