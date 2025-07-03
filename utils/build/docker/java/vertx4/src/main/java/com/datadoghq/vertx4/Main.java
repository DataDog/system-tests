package com.datadoghq.vertx4;

import static datadog.appsec.api.user.User.setUser;
import static java.util.Collections.emptyMap;

import com.datadoghq.system_tests.iast.infra.LdapServer;
import com.datadoghq.system_tests.iast.infra.SqlServer;
import com.datadoghq.system_tests.iast.utils.CryptoExamples;
import com.datadoghq.vertx4.iast.routes.IastSinkRouteProvider;
import com.datadoghq.vertx4.iast.routes.IastSourceRouteProvider;
import com.datadoghq.vertx4.rasp.RaspRouteProvider;
import datadog.appsec.api.blocking.Blocking;
import datadog.appsec.api.login.EventTrackerV2;
import datadog.trace.api.EventTracker;
import datadog.trace.api.interceptor.MutableSpan;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import io.vertx.core.MultiMap;
import io.vertx.core.Vertx;
import io.vertx.core.http.HttpServer;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import io.vertx.ext.web.Session;
import io.vertx.ext.web.handler.BodyHandler;
import io.vertx.core.json.JsonObject;
import io.vertx.core.http.HttpClient;

import javax.naming.directory.InitialDirContext;
import javax.sql.DataSource;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.UndeclaredThrowableException;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;
import java.util.logging.LogManager;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Optional;

import io.vertx.ext.web.handler.SessionHandler;
import io.vertx.ext.web.sstore.LocalSessionStore;
import okhttp3.*;

public class Main {
    static {
        try {
            try (InputStream resourceAsStream = Main.class.getClassLoader().getResourceAsStream("logging.properties")) {
                LogManager.getLogManager().readConfiguration(resourceAsStream);
            }
        } catch (IOException e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    private static final OkHttpClient client = new OkHttpClient();
    private static final CryptoExamples cryptoExamples = new CryptoExamples();

    public static void main(String[] args) {
        Vertx vertx = Vertx.vertx();
        HttpServer server = vertx.createHttpServer();

        Router router = Router.router(vertx);

        router.get("/")
                .produces("text/plain")
                .handler(ctx -> {
                    var tracer = GlobalTracer.get();
                    Span span = tracer.buildSpan("test-span").start();
                    span.setTag("test-tag", "my value");
                    try {
                        ctx.response().setStatusCode(200).end("Hello World!");
                    } finally {
                        span.finish();
                    }
                });

        router.get("/healthcheck").handler(Main::healthCheck);

        router.get("/headers")
                .produces("text/plain")
                .handler(ctx -> ctx.response()
                        .putHeader("content-type", "text/plain")
                        .putHeader("content-length", "42")
                        .putHeader("content-language", "en-US")
                        .end("012345678901234567890123456789012345678901"));
        router.route("/tag_value/:tag_value/:status_code")
                .handler(BodyHandler.create())
                .handler(ctx -> {
                    final Object body = consumeParsedBody(ctx);
                    final String value = ctx.pathParam("tag_value");
                    setRootSpanTag("appsec.events.system_tests_appsec_event.value", value);
                    ctx.response().setStatusCode(Integer.parseInt(ctx.pathParam("status_code")));
                    final String xOption = ctx.request().getParam("X-option");
                    if (xOption != null) {
                        ctx.response().putHeader("X-option", xOption);
                    }
                    if (value.startsWith("payload_in_response_body")) {
                        ctx.response().putHeader("Content-Type", "application/json");
                        ctx.json(new JsonObject().put("payload", body));
                    } else {
                        ctx.response()
                                .putHeader("Content-Type", "text/plain")
                                .end("Value tagged");
                    }
                });
        router.get("/sample_rate_route/:i")
                .handler(ctx -> {
                    final int i = Integer.parseInt(ctx.pathParam("i"));
                    ctx.response().setStatusCode(200).end("OK\n");
                });
        router.get("/api_security/sampling/:i")
                .produces("text/plain")
                .handler(ctx -> {
                    ctx.response()
                            .setStatusCode(Integer.parseInt(ctx.pathParam("i")))
                            .end("Hello!\n");
                });
        router.get("/api_security_sampling/:i")
                .produces("text/plain")
                .handler(ctx -> {
                    final int i = Integer.parseInt(ctx.pathParam("i"));
                    ctx.response()
                            .setStatusCode(200)
                            .end("Hello!\n");
                });
        router.getWithRegex("/params(?:/([^/]*))?(?:/([^/]*))?(?:/([^/]*))?(?:/([^/]*))?(?:/([^/]*))?")
                .produces("text/plain")
                .handler(ctx ->
                        ctx.response().setStatusCode(200).end(ctx.pathParams().toString()));
        router.getWithRegex("/waf(?:/(.*))?").handler(ctx -> {
            // Consume path params
            ctx.pathParams().toString();
            ctx.response().end("Hello world!");
        });
        router.post("/waf").handler(BodyHandler.create());
        router.post("/waf").consumes("application/x-www-form-urlencoded")
                .produces("text/plain")
                .handler(ctx -> {
                    var attrs = ctx.request().formAttributes();
                    ctx.response().setStatusCode(200).end(attrs.toString());
                });
        router.post("/waf").consumes("application/json")
                .handler(ctx -> {
                    var body = ctx.body().buffer();
                    if (body.getByte(0) == '[') {
                        var jsonArrayObj = ctx.body().asJsonArray();
                        ctx.response().setStatusCode(200).end(jsonArrayObj.toString());
                    } else {
                        var jsonObject = ctx.body().asJsonObject();
                        ctx.response().setStatusCode(200).end(jsonObject.toString());
                    }
                });
        for (final String contentType : new String[]{ "text/plain", "application/octet-stream"}) {
            router.post("/waf").consumes(contentType).handler(ctx -> {
                var body = ctx.getBody();
                ctx.response().setStatusCode(200).end(body.toString());
            });
        }
        router.get("/status")
                .handler(ctx -> {
                    String codeString = ctx.request().getParam("code");
                    int code = Integer.parseInt(codeString);
                    ctx.response().setStatusCode(code).end();
                });
        router.get("/stats-unique")
                .handler(ctx -> {
                    String codeString = ctx.request().getParam("code");
                    int code = codeString != null ? Integer.parseInt(codeString): 200;
                    ctx.response().setStatusCode(code).end();
                });
        router.get("/users")
                .handler(ctx -> {
                    final String user = ctx.request().getParam("user");
                    final Span span = GlobalTracer.get().activeSpan();
                    if ((span instanceof MutableSpan)) {
                        MutableSpan localRootSpan = ((MutableSpan) span).getLocalRootSpan();
                        localRootSpan.setTag("usr.id", user);
                    }
                    Blocking.forUser(user).blockIfMatch();
                    ctx.response().end("Hello " + user);
                });
        router.get("/identify").handler(ctx -> {
            final Map<String, String> metadata = new HashMap<>();
            metadata.put("email", "usr.email");
            metadata.put("name", "usr.name");
            metadata.put("session_id", "usr.session_id");
            metadata.put("role", "usr.role");
            metadata.put("scope", "usr.scope");
            setUser("usr.id", metadata);
            ctx.response().end("OK");
        });
        router.get("/user_login_success_event")
                .handler(ctx -> {
                    String event_user_id = ctx.request().getParam("event_user_id");
                    if (event_user_id == null) {
                        event_user_id = "system_tests_user";
                    }
                    datadog.trace.api.GlobalTracer.getEventTracker()
                            .trackLoginSuccessEvent(
                                    event_user_id, METADATA);
                    ctx.response().end("ok");
                });
        router.get("/user_login_failure_event")
                .handler(ctx -> {
                    String event_user_id = ctx.request().getParam("event_user_id");
                    if (event_user_id == null) {
                        event_user_id = "system_tests_user";
                    }
                    String event_user_exists = ctx.request().getParam("event_user_exists");
                    if (event_user_exists == null) {
                        event_user_exists = "true";
                    }
                    datadog.trace.api.GlobalTracer.getEventTracker()
                            .trackLoginFailureEvent(
                                    event_user_id, Boolean.parseBoolean(event_user_exists), METADATA);
                    ctx.response().end("ok");
                });
        router.post("/user_login_success_event_v2")
                .handler(BodyHandler.create())
                .handler(ctx -> {
                    final JsonObject body = ctx.body().asJsonObject();
                    final String login = body.getString("login", "system_tests_login");
                    final String userId = body.getString("user_id", "system_tests_user_id");
                    final Map<String, String> metadata = asMetadataMap(body.getJsonObject("metadata"));
                    EventTrackerV2.trackUserLoginSuccess(login, userId, metadata);
                    ctx.response().end("ok");
                });
        router.post("/user_login_failure_event_v2")
                .handler(BodyHandler.create())
                .handler(ctx -> {
                    final JsonObject body = ctx.body().asJsonObject();
                    final String login = body.getString("login", "system_tests_login");
                    final String exists = body.getString("exists", "true");
                    final Map<String, String> metadata = asMetadataMap(body.getJsonObject("metadata"));
                    EventTrackerV2.trackUserLoginFailure(login, Boolean.parseBoolean(exists), metadata);
                    ctx.response().end("ok");
                });
        router.get("/custom_event")
                .handler(ctx -> {
                    String event_name = ctx.request().getParam("event_name");
                    if (event_name == null) {
                        event_name = "system_tests_event";
                    }
                    datadog.trace.api.GlobalTracer.getEventTracker()
                            .trackCustomEvent(event_name, METADATA);
                    ctx.response().end("ok");
                });
        router.get("/requestdownstream")
                .handler(ctx -> {
                    String url = "http://localhost:7777/returnheaders";
                    Request request = new Request.Builder()
                            .url(url)
                            .build();

                    client.newCall(request).enqueue(new Callback() {
                        @Override
                        public void onFailure(Call call, IOException e) {
                            ctx.response().setStatusCode(500).end(e.getMessage());
                        }

                        @Override
                        public void onResponse(Call call, Response response) throws IOException {
                            if (!response.isSuccessful()) {
                                ctx.response().setStatusCode(500).end(response.message());
                            } else {
                                ctx.response().end(response.body().string());
                            }
                        }
                    });
                });
        router.get("/vulnerablerequestdownstream")
                .handler(ctx -> {
                    cryptoExamples.insecureMd5Hashing("password");
                    String url = "http://localhost:7777/returnheaders";
                    Request request = new Request.Builder()
                            .url(url)
                            .build();

                    client.newCall(request).enqueue(new Callback() {
                        @Override
                        public void onFailure(Call call, IOException e) {
                            ctx.response().setStatusCode(500).end(e.getMessage());
                        }

                        @Override
                        public void onResponse(Call call, Response response) throws IOException {
                            if (!response.isSuccessful()) {
                                ctx.response().setStatusCode(500).end(response.message());
                            } else {
                                ctx.response().end(response.body().string());
                            }
                        }
                    });
                });
        // Custom response headers endpoint
        router.get("/customResponseHeaders")
                .handler(ctx -> {
                    // Set a standard header
                    ctx.response().putHeader("content-language", "en-US");
                    // Set a content-type header as expected by system tests
                    ctx.response().putHeader("content-type", "text/html");
                    // Add five custom test headers
                    for (int i = 1; i <= 5; i++) {
                        ctx.response().putHeader("X-Test-Header-" + i, "value" + i);
                    }
                    ctx.response().end("Response with custom headers");
                });

        // Exceed response headers endpoint
        router.get("/exceedResponseHeaders")
                .handler(ctx -> {
                    // Add fifty custom test headers
                    io.vertx.core.http.HttpServerResponse resp = ctx.response();
                    for (int i = 1; i <= 50; i++) {
                        resp.putHeader("X-Test-Header-" + i, "value" + i);
                    }
                    // Ensure content-language is included
                    resp.putHeader("content-language", "en-US");
                    // Set a content-type header as expected by system tests
                    resp.putHeader("content-type", "text/html");
                    resp.end("Response with more than 50 headers");
                });
        router.get("/returnheaders")
                .handler(ctx -> {
                    JsonObject headersJson = new JsonObject();
                    ctx.request().headers().forEach(header -> headersJson.put(header.getKey(), header.getValue()));
                    ctx.response().end(headersJson.encode());
                });
        router.get("/set_cookie")
                .handler(ctx -> {
                    String name = ctx.request().getParam("name");
                    String value = ctx.request().getParam("value");
                    ctx.response().putHeader("Set-Cookie", name + "=" + value).end("ok");
                });
        router.get("/createextraservice")
                .handler(ctx -> {
                    String serviceName = ctx.request().getParam("serviceName");
                    setRootSpanTag("service", serviceName);
                    ctx.response().end("ok");
                });

        Router sessionRouter = Router.router(vertx);
        sessionRouter.get().handler(SessionHandler.create(LocalSessionStore.create(vertx)));
        sessionRouter.get("/new")
                .handler(ctx -> {
                    final Session session = ctx.session();
                    ctx.response().end(session.id());
                });
        sessionRouter.get("/user")
                .handler(ctx -> {
                    final Session session = ctx.session();
                    final String sdkUser = ctx.request().getParam("sdk_user");
                    EventTracker tracker = datadog.trace.api.GlobalTracer.getEventTracker();
                    tracker.trackLoginSuccessEvent(sdkUser, emptyMap());
                    ctx.response().end(session.id());
                });
        router.get("/session/*").subRouter(sessionRouter);

        iastRouteProviders().forEach(provider -> provider.accept(router));
        raspRouteProviders().forEach(provider -> provider.accept(router));
        server.requestHandler(router).listen(7777);
    }

    private static Stream<Consumer<Router>> iastRouteProviders() {
        return Stream.of(new IastSinkRouteProvider(DATA_SOURCE, LDAP_CONTEXT), new IastSourceRouteProvider(DATA_SOURCE));
    }

    private static Stream<Consumer<Router>> raspRouteProviders() {
        return Stream.of(new RaspRouteProvider(DATA_SOURCE));
    }

    private static Map<String, String> asMetadataMap(final JsonObject metadata) {
        if (metadata == null) {
            return emptyMap();
        }
        return metadata.stream()
                .collect(Collectors.toMap(
                        Map.Entry::getKey,
                        entry -> entry.getValue().toString()

                ));
    }

    private static final Map<String, String> METADATA = createMetadata();

    private static final Map<String, String> createMetadata() {
        HashMap<String, String> h = new HashMap<>();
        h.put("metadata0", "value0");
        h.put("metadata1", "value1");
        return h;
    }

    private static final DataSource DATA_SOURCE = new SqlServer().start();

    private static final InitialDirContext LDAP_CONTEXT = new LdapServer().start();

    private static void setRootSpanTag(final String key, final String value) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span instanceof MutableSpan) {
            final MutableSpan rootSpan = ((MutableSpan) span).getLocalRootSpan();
            if (rootSpan != null) {
                rootSpan.setTag(key, value);
            }
        }
    }

    private static Object consumeParsedBody(final RoutingContext ctx) {
        String contentType = ctx.request().getHeader("Content-Type");
        if (contentType == null) {
            return ctx.body().asString();
        }
        contentType = contentType.toLowerCase(Locale.ROOT);
        if (contentType.contains("json")) {
            return ctx.body().asJsonObject();
        } else if (contentType.equals("application/x-www-form-urlencoded")) {
            final Map<String, List<String>> result = new HashMap<>();
            final MultiMap form = ctx.request().formAttributes();
            for (final String key : form.names()) {
                result.put(key, form.getAll(key));
            }
            return result;
        } else {
            return ctx.body().asString();
        }
    }

    private static void healthCheck(RoutingContext context) {
        String version = getVersion().orElse("0.0.0");

        Map<String, Object> response = new HashMap<>();
        Map<String, String> library = new HashMap<>();
        library.put("name", "java");
        library.put("version", version);
        response.put("status", "ok");
        response.put("library", library);

        JsonObject jsonResponse = new JsonObject(response);

        context.response()
            .putHeader("content-type", "application/json")
            .end(jsonResponse.encode());
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
}
