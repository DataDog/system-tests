package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.iast.utils.PathExamples;
import com.datadoghq.system_tests.iast.utils.SqlExamples;
import com.datadoghq.system_tests.iast.utils.TestBean;
import com.datadoghq.system_tests.springboot.kafka.KafkaConnector;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.context.request.async.DeferredResult;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.ServletRequest;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.sql.DataSource;

import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.function.Predicate;

@SuppressWarnings("Convert2MethodRef")
@RestController
@RequestMapping("/iast/source")
@EnableAsync
public class AppSecIastSource {

    private final SqlExamples sql;

    private final PathExamples path;

    public AppSecIastSource(final DataSource dataSource) {
        this.sql = new SqlExamples(dataSource);
        this.path = new PathExamples();
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

    @GetMapping("/kafkakey/test")
    public DeferredResult<ResponseEntity<String>> kafkaKey() throws Exception {
        return kafka("hello key!", "value", record -> Paths.get(record.key()).toString());
    }

    @GetMapping("/kafkavalue/test")
    public DeferredResult<ResponseEntity<String>> kafkaValue() throws Exception {
        return kafka("key", "hello value!", record -> Paths.get(record.value()).toString());
    }

    private DeferredResult<ResponseEntity<String>> kafka(final String key, final String value, final KafkaRecordHandler op) throws Exception {
        final KafkaConnector connector = new KafkaConnector();
        final long timeout = TimeUnit.SECONDS.toMillis(10);
        final ResponseEntity<String> timeoutResult = ResponseEntity.internalServerError().body("Failed to consume messages");
        final DeferredResult<ResponseEntity<String>> result = new DeferredResult<>(timeout, timeoutResult);
        connector.startConsumingMessages("iast-group", records -> {
            for (ConsumerRecord<String, String> record : records) {
                if (key.equals(record.key())) {
                    System.out.println("got record! " + record.key() + ":" + record.value() + " from " + record.topic());
                    result.setResult(ResponseEntity.ok(op.handle(record)));
                    return true;
                }
            }
            return false;
        });
        connector.produceMessageWithoutNewThread(key, value);
        return result;
    }

    @SuppressWarnings("OptionalGetWithoutIsPresent")
    private <E> String find(final Collection<E> list, final Predicate<E> matcher, final Function<E, String> provider) {
        return provider.apply(list.stream().filter(matcher).findFirst().get());
    }

    private String find(final Collection<String> list, final Predicate<String> matcher) {
        return find(list, matcher, Function.identity());
    }

    private interface KafkaRecordHandler {
        String handle(ConsumerRecord<String, String> record);
    }

}
