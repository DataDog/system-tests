package com.datadoghq.ratpack;

import static datadog.appsec.api.user.User.setUser;
import static java.util.Collections.emptyMap;

import com.datadoghq.system_tests.iast.infra.SqlServer;
import com.datadoghq.system_tests.iast.utils.CryptoExamples;
import datadog.trace.api.interceptor.MutableSpan;
import datadog.trace.api.internal.InternalTracer;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import ratpack.exec.Blocking;
import ratpack.exec.Promise;
import ratpack.http.HttpMethod;
import ratpack.http.Response;
import ratpack.server.RatpackServer;
import ratpack.jackson.Jackson;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.lang.reflect.UndeclaredThrowableException;
import java.net.InetAddress;
import java.util.logging.LogManager;
import java.util.Optional;

import java.util.HashMap;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.List;
import ratpack.util.MultiValueMap;
import ratpack.handling.Context;
import ratpack.handling.Handler;
import ratpack.http.Headers;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.datadoghq.system_tests.iast.utils.Utils;
import com.datadoghq.system_tests.iast.utils.CryptoExamples;

import javax.sql.DataSource;

/**
 * Main class.
 *
 */
public class Main {
    static {
        try {
            try (InputStream resourceAsStream = Main.class.getClassLoader().getResourceAsStream("logging.properties")) {
                LogManager.getLogManager().readConfiguration(
                        resourceAsStream);
            }
        } catch (IOException e) {
            throw new UndeclaredThrowableException(e);
        }
    }


    private static final Map<String, String> METADATA = createMetadata();
    private static final Map<String, String> createMetadata() {
        HashMap<String, String> h = new HashMap<>();
        h.put("metadata0", "value0");
        h.put("metadata1", "value1");
        return h;
    }

    private static Optional<String> getVersion() {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(Main.class.getClassLoader().getResourceAsStream("dd-java-agent.version"), StandardCharsets.ISO_8859_1))) {
        String line = reader.readLine();
        return Optional.ofNullable(line);
        } catch (Exception e) {
        return Optional.empty();
        }
    }

    private static void setRootSpanTag(final String key, final String value) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span instanceof MutableSpan) {
            final MutableSpan rootSpan = ((MutableSpan) span).getLocalRootSpan();
            if (rootSpan != null) {
                rootSpan.setTag(key, value);
            }
        }
    }

    private static final CryptoExamples cryptoExamples = new CryptoExamples();

    public static void main(String[] args) throws Exception {

        var iastHandlers = new IastHandlers();
        var raspHandlers = new RaspHandlers();
        var server = RatpackServer.start(s ->
                s.serverConfig(action -> action
                        .address(InetAddress.getByName("0.0.0.0"))
                        .port(7777)
                ).handlers(chain -> {
                    chain
                            .get("", ctx -> {
                                var tracer = GlobalTracer.get();
                                Span span = tracer.buildSpan("test-span").start();
                                span.setTag("test-tag", "my value");
                                try {
                                    ctx.getResponse().send("text/plain", "Hello World!");
                                } finally {
                                    span.finish();
                                }
                            })
                            .get("healthcheck", ctx -> {
                                String version = getVersion().orElse("0.0.0");

                                Map<String, Object> response = new HashMap<>();
                                Map<String, String> library = new HashMap<>();
                                library.put("language", "java");
                                library.put("version", version);
                                response.put("status", "ok");
                                response.put("library", library);

                                ctx.render(Jackson.json(response));
                            })
                            .get("headers", ctx -> {
                                Response response = ctx.getResponse();
                                response.getHeaders()
                                        .add("content-language", "en-US");
                                response.send("text/plain", "012345678901234567890123456789012345678901");
                            })
                            .get("make_distant_call", ctx -> {
                                final Promise<String> res = Blocking.get(() -> {
                                    String url = ctx.getRequest().getQueryParams().get("url");

                                    URL urlObject = new URL(url);

                                    HttpURLConnection con = (HttpURLConnection) urlObject.openConnection();
                                    con.setRequestMethod("GET");

                                    // Save request headers
                                    HashMap<String, String> request_headers = new HashMap<String, String>();
                                    for (Map.Entry<String, List<String>> header : con.getRequestProperties().entrySet()) {
                                        if (header.getKey() == null) {
                                            continue;
                                        }

                                        request_headers.put(header.getKey(), header.getValue().get(0));
                                    }

                                    // Save response headers and status code
                                    int status_code = con.getResponseCode();
                                    HashMap<String, String> response_headers = new HashMap<String, String>();
                                    for (Map.Entry<String, List<String>> header : con.getHeaderFields().entrySet()) {
                                        if (header.getKey() == null) {
                                            continue;
                                        }

                                        response_headers.put(header.getKey(), header.getValue().get(0));
                                    }

                                    DistantCallResponse result = new DistantCallResponse();
                                    result.url = url;
                                    result.status_code = status_code;
                                    result.request_headers = request_headers;
                                    result.response_headers = response_headers;

                                    return (new ObjectMapper()).writeValueAsString(result);
                                });
                                res.then((r) -> {
                                    Response response = ctx.getResponse();
                                    response.send("application/json", r);
                                });
                            })
                            .path("tag_value/:tag_value/:status_code", ctx -> {
                                final String value = ctx.getPathTokens().get("tag_value");
                                final int code = Integer.parseInt(ctx.getPathTokens().get("status_code"));
                                WafPostHandler.consumeParsedBody(ctx).then(v -> {
                                    setRootSpanTag("appsec.events.system_tests_appsec_event.value", value);
                                    ctx.getResponse().status(code).send("Value tagged");
                                });
                            })
                            .get("sample_rate_route/:i", ctx -> {
                                final int i = Integer.parseInt(ctx.getPathTokens().get("i"));
                                ctx.getResponse().status(200).send("OK\n");
                            })
                            .get("api_security/sampling/:i", ctx -> {
                                final int i = Integer.parseInt(ctx.getPathTokens().get("i"));
                                ctx.getResponse().status(i).send("Hello!\n");
                            })
                            .get("api_security_sampling/:i", ctx -> {
                                final int i = Integer.parseInt(ctx.getPathTokens().get("i"));
                                ctx.getResponse().status(200).send("OK!\n");
                            })
                            .path("waf/:params?", ctx -> {
                                HttpMethod method = ctx.getRequest().getMethod();
                                if (method.equals(HttpMethod.GET)) {
                                    ctx.getResponse().send("text/plain", "(empty url params)");
                                } else if (method.equals(HttpMethod.POST)) {
                                    ctx.insert(new WafPostHandler());
                                } else {
                                    ctx.next();
                                }
                            })
                            .get("params/:params?:.*",
                                    ctx -> ctx.getResponse().send("text/plain", ctx.getPathTokens().toString()))
                            .path("status", ctx -> {
                                String codeParam = ctx.getRequest().getQueryParams().get("code");
                                int code = Integer.parseInt(codeParam);
                                ctx.getResponse().status(code).send();
                            })
                            .get("users", ctx -> {
                                final String user = ctx.getRequest().getQueryParams().get("user");
                                final Span span = GlobalTracer.get().activeSpan();
                                if ((span instanceof MutableSpan)) {
                                    MutableSpan localRootSpan = ((MutableSpan) span).getLocalRootSpan();
                                    localRootSpan.setTag("usr.id", user);
                                }
                                datadog.appsec.api.blocking.Blocking.forUser(user).blockIfMatch();
                                ctx.getResponse().send("text/plain", "Hello " + user);
                            })
                            .get("identify", ctx -> {
                                final Map<String, String> metadata = new HashMap<>();
                                metadata.put("email", "usr.email");
                                metadata.put("name", "usr.name");
                                metadata.put("session_id", "usr.session_id");
                                metadata.put("role", "usr.role");
                                metadata.put("scope", "usr.scope");
                                setUser("usr.id", metadata);
                                ctx.getResponse().send("text/plain", "OK");
                            })
                            .get("user_login_success_event", ctx -> {
                                MultiValueMap<String, String> qp = ctx.getRequest().getQueryParams();
                                datadog.trace.api.GlobalTracer.getEventTracker()
                                        .trackLoginSuccessEvent(
                                                qp.getOrDefault("event_user_id", "system_tests_user"), METADATA);
                                ctx.getResponse().send("ok");
                            })
                            .get("user_login_failure_event", ctx -> {
                                MultiValueMap<String, String> qp = ctx.getRequest().getQueryParams();
                                datadog.trace.api.GlobalTracer.getEventTracker()
                                        .trackLoginFailureEvent(
                                                qp.getOrDefault("event_user_id", "system_tests_user"),
                                                Boolean.parseBoolean(qp.getOrDefault("event_user_exists", "true")),
                                                METADATA);
                                ctx.getResponse().send("ok");
                            })
                            .get("custom_event", ctx -> {
                                MultiValueMap<String, String> qp = ctx.getRequest().getQueryParams();
                                datadog.trace.api.GlobalTracer.getEventTracker()
                                        .trackCustomEvent(
                                                qp.getOrDefault("event_name", "system_tests_event"), METADATA);
                                ctx.getResponse().send("ok");
                            })
                            .get("requestdownstream", ctx -> {
                                final Promise<String> res = Blocking.get(() -> {
                                    String url = "http://localhost:7777/returnheaders";
                                    return Utils.sendGetRequest(url);
                                });
                                res.then((r) -> {
                                    Response response = ctx.getResponse();
                                    response.send("application/json", r);
                                });
                            })
                            .get("vulnerablerequestdownstream", ctx -> {
                                final Promise<String> res = Blocking.get(() -> {
                                    cryptoExamples.insecureMd5Hashing("password");
                                    String url = "http://localhost:7777/returnheaders";
                                    return Utils.sendGetRequest(url);
                                });
                                res.then((r) -> {
                                    Response response = ctx.getResponse();
                                    response.send("application/json", r);
                                });
                            })
                            .get("returnheaders", ctx -> {
                                Headers headers = ctx.getRequest().getHeaders();
                                Map<String, String> headerMap = new HashMap<>();
                                headers.getNames().forEach(name -> headerMap.put(name, headers.get(name)));

                                ObjectMapper mapper = new ObjectMapper();
                                String json = mapper.writeValueAsString(headerMap);

                                ctx.getResponse().send("application/json", json);
                            })
                            .get("createextraservice", ctx -> {
                                MultiValueMap<String, String> qp = ctx.getRequest().getQueryParams();
                                String serviceName = qp.get("serviceName");
                                setRootSpanTag("service", serviceName);
                                ctx.getResponse().send("ok");
                            })
                            .get("set_cookie", ctx -> {
                                final String name = ctx.getRequest().getQueryParams().get("name");
                                final String value = ctx.getRequest().getQueryParams().get("value");
                                ctx.getResponse().getHeaders().add("Set-Cookie", name + "=" + value);
                                ctx.getResponse().send("text/plain", "ok");
                            });
                        iastHandlers.setup(chain);
                        raspHandlers.setup(chain);
                })
        );
        System.out.println("Ratpack server started on port 7777");
        while (!Thread.interrupted()) {
            try {
                Thread.sleep(60000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        server.stop();
    }

    public static final class DistantCallResponse {
        public String url;
        public int status_code;
        public HashMap<String, String> request_headers;
        public HashMap<String, String> response_headers;
    }

    public static final DataSource DATA_SOURCE = new SqlServer().start();
}

