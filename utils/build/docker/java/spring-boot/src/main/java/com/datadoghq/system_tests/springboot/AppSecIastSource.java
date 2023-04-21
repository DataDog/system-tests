package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.iast.utils.*;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.ServletRequest;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.sql.DataSource;
import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/iast/source")
public class AppSecIastSource {

    private final SqlExamples sql;

    public AppSecIastSource(final DataSource dataSource) {
        this.sql = new SqlExamples(dataSource);
    }


    @PostMapping("/parameter/test")
    String sourceParameter(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String source = request.getParameter("source");
        sql.insecureSql(source, source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", source);
    }

    @PostMapping("/parametername/test")
    String sourceParameterName(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        List<String> parameterNames = Collections.list(request.getParameterNames());
        final String source = parameterNames.get(0);
        sql.insecureSql(source, source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameter Names => %s", parameterNames);
    }

    @GetMapping("/headername/test")
    String sourceHeaderName(final HttpServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        List<String> headerNames = Collections.list(request.getHeaderNames());
        String headerName =  headerNames.stream().filter(name -> name.equals("random-key")).findFirst().get();
        sql.insecureSql(headerName, headerName, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", headerNames);
    }

    @GetMapping("/header/test")
    String sourceHeaders(@RequestHeader("random-key") String header) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        sql.insecureSql(header, header, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", header);
    }

    @GetMapping("/cookiename/test")
    String sourceCookieName(final HttpServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        Cookie[] cookies = request.getCookies();
        for (Cookie cookie : cookies) {
            String name = cookie.getName();
            sql.insecureSql(name, name, (statement, sql) -> statement.executeQuery(sql));
            break;
        }
        return String.format("Request Cookies => %s", cookies);
    }

    @GetMapping("/cookievalue/test")
    String sourceCookieValue(final HttpServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        Cookie[] cookies = request.getCookies();
        for (Cookie cookie : cookies) {
            String value = cookie.getValue();
            sql.insecureSql(value, value, (statement, sql) -> statement.executeQuery(sql));
            break;
        }
        return String.format("Request Cookies => %s", cookies);
    }

    @PostMapping("/body/test")
    String sourceBody(@RequestBody TestBean testBean) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        String name = testBean.getName();
        String value = testBean.getValue();
        sql.insecureSql(name, value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("@RequestBody to Test bean -> name: %s, value:%s", name, value);
    }

}
