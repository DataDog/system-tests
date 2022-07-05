package com.datadoghq.ratpack;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import ratpack.http.HttpMethod;
import ratpack.http.Response;
import ratpack.server.RatpackServer;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.UndeclaredThrowableException;
import java.net.InetAddress;
import java.util.logging.LogManager;

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

    public static void main(String[] args) throws Exception {
        var server = RatpackServer.start(s ->
                s.serverConfig(action -> action
                        .address(InetAddress.getByName("0.0.0.0"))
                        .port(7777)
                ).handlers(chain -> chain
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
                        .get("headers", ctx -> {
                            Response response = ctx.getResponse();
                            response.getHeaders()
                                    .add("content-language", "en-US");
                            response.send("text/plain", "012345678901234567890123456789012345678901");
                        })
                        .path("waf", ctx -> {
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
                )
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
}

