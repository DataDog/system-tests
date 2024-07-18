package com.datadoghq.vertx3;

import com.datadoghq.system_tests.iast.infra.LdapServer;
import com.datadoghq.system_tests.iast.infra.SqlServer;
import com.datadoghq.vertx3.iast.routes.IastSinkRouteProvider;
import com.datadoghq.vertx3.iast.routes.IastSourceRouteProvider;
import com.datadoghq.vertx3.rasp.RaspRouteProvider;
import datadog.appsec.api.blocking.Blocking;
import datadog.trace.api.interceptor.MutableSpan;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import io.vertx.core.Vertx;
import io.vertx.core.http.HttpServer;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import io.vertx.ext.web.handler.BodyHandler;
import io.vertx.core.json.JsonObject;
import io.vertx.core.http.HttpClient;

import javax.naming.directory.InitialDirContext;
import javax.sql.DataSource;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.UndeclaredThrowableException;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;
import java.util.logging.LogManager;
import java.util.stream.Stream;

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
        router.get("/headers")
                .produces("text/plain")
                .handler(ctx -> ctx.response()
                        .putHeader("content-type", "text/plain")
                        .putHeader("content-length", "42")
                        .putHeader("content-language", "en-US")
                        .end("012345678901234567890123456789012345678901"));
        router.routeWithRegex("/tag_value/(?<value>[^/]+)/(?<code>[0-9]+)")
                .handler(BodyHandler.create())
                .produces("text/plain")
                .handler(ctx -> {
                    consumeParsedBody(ctx);
                    setRootSpanTag("appsec.events.system_tests_appsec_event.value", ctx.pathParam("value"));
                    ctx.response()
                            .setStatusCode(Integer.parseInt(ctx.pathParam("code")))
                            .end("Value tagged");
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
                    var body = ctx.getBody();
                    if (body.getByte(0) == '[') {
                        var jsonArrayObj = ctx.getBodyAsJsonArray();
                        ctx.response().setStatusCode(200).end(jsonArrayObj.toString());
                    } else {
                        var jsonObject = ctx.getBodyAsJson();
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
        router.get("/returnheaders")
                .handler(ctx -> {
                    JsonObject headersJson = new JsonObject();
                    ctx.request().headers().forEach(header -> headersJson.put(header.getKey(), header.getValue()));
                    ctx.response().end(headersJson.encode());
                });

        iastRouteProviders().forEach(provider -> provider.accept(router));
        raspRouteProviders().forEach(provider -> provider.accept(router));
        server.requestHandler(router::accept).listen(7777);
    }

    private static Stream<Consumer<Router>> iastRouteProviders() {
        return Stream.of(new IastSinkRouteProvider(DATA_SOURCE, LDAP_CONTEXT), new IastSourceRouteProvider(DATA_SOURCE));
    }

    private static Stream<Consumer<Router>> raspRouteProviders() {
        return Stream.of(new RaspRouteProvider(DATA_SOURCE));
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

    private static void consumeParsedBody(final RoutingContext ctx) {
        String contentType = ctx.request().getHeader("Content-Type");
        if (contentType == null) {
            return;
        }
        contentType = contentType.toLowerCase(Locale.ROOT);
        if (contentType.contains("json")) {
            ctx.getBodyAsJson();
        } else if (contentType.equals("application/x-www-form-urlencoded")) {
            ctx.request().formAttributes();
        } else {
            ctx.getBodyAsString();
        }
    }
}
