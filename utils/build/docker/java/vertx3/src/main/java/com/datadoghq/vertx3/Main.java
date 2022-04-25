package com.datadoghq.vertx3;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import io.vertx.core.Vertx;
import io.vertx.core.http.HttpServer;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.handler.BodyHandler;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.UndeclaredThrowableException;
import java.util.logging.LogManager;

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
        router.getWithRegex("/params(?:/([^/]*))?(?:/([^/]*))?(?:/([^/]*))?(?:/([^/]*))?(?:/([^/]*))?")
                .produces("text/plain")
                .handler(ctx ->
                        ctx.response().setStatusCode(200).end(ctx.pathParams().toString()));
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

        server.requestHandler(router::accept).listen(7777);
    }


}
