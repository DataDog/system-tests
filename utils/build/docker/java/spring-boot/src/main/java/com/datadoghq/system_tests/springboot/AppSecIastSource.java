package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.iast.utils.SqlExamples;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.ServletRequest;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/iast/source")
public class AppSecIastSource {


    @PostMapping("/parameter/test")
    String sourceParameter(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String source = request.getParameter("source");
        final String value = request.getParameter("value");
        return String.format("Request Parameters => source: %s, value: %s", source, value);
    }

    @PostMapping("/parametername/test")
    String sourceParameterName(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        List<String> parameterNames = Collections.list(request.getParameterNames());
        return String.format("Request Parameter Names => %s", parameterNames);
    }

    @GetMapping("/headername/test")
    String sourceHeaderName(final HttpServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        List<String> headerNames = Collections.list(request.getHeaderNames());
        return String.format("Request Headers => %s", headerNames);
    }

    @GetMapping("/header/test")
    String sourceHeaders(@RequestHeader("random-key") String header) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return String.format("Request Headers => %s", header);
    }

    @GetMapping("/cookie/test")
    String sourceCookies(final HttpServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        Cookie[] cookies = request.getCookies();
        for (Cookie cookie : cookies) {
            cookie.getName();
            cookie.getValue();
        }
        return String.format("Request Cookies => %s", cookies);
    }

}
