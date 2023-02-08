package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.iast.utils.TestBean;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.beans.factory.annotation.Autowired;
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
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/iast/source")
public class AppSecIastSource {

    @Autowired
    private DataSource dataSource;


    @PostMapping("/parameter/test")
    String sourceParameter(final ServletRequest request) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String source = request.getParameter("source");
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + source + "' AND PASSWORD = '" + source + "'";
            statement.executeQuery(sql);
        }
        return String.format("Request Parameters => source: %s", source);
    }

    @PostMapping("/parametername/test")
    String sourceParameterName(final ServletRequest request) throws SQLException  {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        List<String> parameterNames = Collections.list(request.getParameterNames());
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + parameterNames.get(0) + "' AND PASSWORD = '" + parameterNames.get(0) + "'";
            statement.executeQuery(sql);
        }
        return String.format("Request Parameter Names => %s", parameterNames);
    }

    @GetMapping("/headername/test")
    String sourceHeaderName(final HttpServletRequest request) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        List<String> headerNames = Collections.list(request.getHeaderNames());
        String headerName =  headerNames.stream().filter(name -> name.equals("random-key")).findFirst().get();
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + headerName + "' AND PASSWORD = '" + headerName + "'";
            statement.executeQuery(sql);
        }
        return String.format("Request Headers => %s", headerNames);
    }

    @GetMapping("/header/test")
    String sourceHeaders(@RequestHeader("random-key") String header) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + header + "' AND PASSWORD = '" + header + "'";
            statement.executeQuery(sql);
        }
        return String.format("Request Headers => %s", header);
    }

    @GetMapping("/cookiename/test")
    String sourceCookieName(final HttpServletRequest request) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        Cookie[] cookies = request.getCookies();
        for (Cookie cookie : cookies) {
            String name = cookie.getName();
            try (final Connection con = dataSource.getConnection()) {
                final Statement statement = con.createStatement();
                final String sql = "SELECT * FROM USER WHERE USERNAME = '" + name + "' AND PASSWORD = '" + name + "'";
                statement.executeQuery(sql);
            }
            break;
        }
        return String.format("Request Cookies => %s", cookies);
    }

    @GetMapping("/cookievalue/test")
    String sourceCookieValue(final HttpServletRequest request) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        Cookie[] cookies = request.getCookies();
        for (Cookie cookie : cookies) {
            String value = cookie.getValue();
            try (final Connection con = dataSource.getConnection()) {
                final Statement statement = con.createStatement();
                final String sql = "SELECT * FROM USER WHERE USERNAME = '" + value + "' AND PASSWORD = '" + value + "'";
                statement.executeQuery(sql);
            }
            break;
        }
        return String.format("Request Cookies => %s", cookies);
    }

    @PostMapping("/body/test")
    String sourceBody(@RequestBody TestBean testBean) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        String name = testBean.getName();
        String value = testBean.getValue();
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + name + "' AND PASSWORD = '" + value + "'";
            statement.executeQuery(sql);
        }
        return String.format("@RequestBody to Test bean -> name: %s, value:%", name, value);
    }

}
