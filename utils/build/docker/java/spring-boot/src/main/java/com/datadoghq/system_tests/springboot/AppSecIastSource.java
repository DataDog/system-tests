package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.iast.utils.SqlExamples;
import com.datadoghq.system_tests.iast.utils.TestBean;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.ServletRequest;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.sql.DataSource;

import java.io.BufferedReader;
import java.io.IOException;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.stream.Collectors;

@SuppressWarnings("Convert2MethodRef")
@RestController
@RequestMapping("/iast/source")
public class AppSecIastSource {

    private final SqlExamples sql;

    public AppSecIastSource(final DataSource dataSource) {
        this.sql = new SqlExamples(dataSource);
    }

    @GetMapping("/parameter/test")
    String sourceParameterGet(final ServletRequest request) {
        final String table = request.getParameter("table");
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", table);
    }

    @PostMapping("/parameter/test")
    String sourceParameterPost(final ServletRequest request) {
        final String table = request.getParameter("table");
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", table);
    }

    @GetMapping("/parametername/test")
    String sourceParameterNameGet(final ServletRequest request) {
        List<String> parameterNames = Collections.list(request.getParameterNames());
        final String table = parameterNames.get(0);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameter Names => %s", parameterNames);
    }

    @PostMapping("/parametername/test")
    String sourceParameterNamePost(final ServletRequest request) {
        List<String> parameterNames = Collections.list(request.getParameterNames());
        final String table = parameterNames.get(0);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameter Names => %s", parameterNames);
    }
    @GetMapping("/headername/test")
    String sourceHeaderName(final HttpServletRequest request) {
        List<String> headerNames = Collections.list(request.getHeaderNames());
        String table = find(headerNames, header -> header.equalsIgnoreCase("user"));
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", headerNames);
    }

    @GetMapping("/header/test")
    String sourceHeaders(@RequestHeader("table") String table) {
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", table);
    }

    @GetMapping("/cookiename/test")
    String sourceCookieName(final HttpServletRequest request) {
        List<Cookie> cookies = Arrays.asList(request.getCookies());
        final String table = find(cookies, c -> c.getName().equalsIgnoreCase("user"), Cookie::getName);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", cookies);
    }

    @GetMapping("/cookievalue/test")
    String sourceCookieValue(final HttpServletRequest request) {
        List<Cookie> cookies = Arrays.asList(request.getCookies());
        final String table = find(cookies, c -> c.getName().equalsIgnoreCase("table"), Cookie::getValue);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", cookies);
    }

    @PostMapping("/body/test")
    String sourceBody(@RequestBody TestBean testBean) {
        String value = testBean.getValue();
        sql.insecureSql(value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("@RequestBody to Test bean -> value:%s", value);
    }

    @GetMapping("/uri/test")
    String uriTest(HttpServletRequest request) {
        StringBuffer url = request.getRequestURL();
        String urlString = url.toString();
        String param = urlString.substring(url.lastIndexOf("/") +1 , url.length());
        try {
        sql.insecureSql(param, (statement, sql) -> {
                statement.executeQuery(sql);
                return null;
        });
        } catch (Exception ex) {
            // Using table that does not exist, ignore error.
        }
        return "OK";
    }

    @PostMapping("/multipart/test")
    public String handleFileUpload(@RequestParam("file1") MultipartFile file) {
        String fileName = file.getName();
        sql.insecureSql(fileName, (statement, sql) -> {
            try {
                statement.executeQuery(sql);
            } catch (Exception ex) {
                // Using table that does not exist, ignore error.
            }
            return null;
        });
        return "fileName: " + file.getName();
    }

    @GetMapping("/path/test")
    String sourcePath(HttpServletRequest request) {
        String path = request.getRequestURI();
        String param = path.substring(path.lastIndexOf('/'));
        sql.insecureSql(param, (statement, sql) -> {
            try {
                statement.executeQuery(sql);
            } catch (Exception ex) {
                // Using table that does not exist, ignore error.
            }
            return null;
        });
        return "OK";
    }

    @SuppressWarnings("OptionalGetWithoutIsPresent")
    private <E> String find(final Collection<E> list,
                            final Predicate<E> matcher,
                            final Function<E, String> provider) {
        return provider.apply(list.stream().filter(matcher).findFirst().get());
    }

    private String find(final Collection<String> list,
                        final Predicate<String> matcher) {
        return find(list, matcher, Function.identity());
    }

}
