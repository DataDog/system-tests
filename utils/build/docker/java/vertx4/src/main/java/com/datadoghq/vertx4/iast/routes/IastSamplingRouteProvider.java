package com.datadoghq.vertx4.iast.routes;

import io.vertx.core.Handler;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.function.Consumer;

public class IastSamplingRouteProvider implements Consumer<Router> {
    @Override
    public void accept(Router router) {
        // GET /iast/sampling-by-route-method-count/:id
        router.get("/iast/sampling-by-route-method-count/:id").handler(ctx -> {
            try {
                String id = ctx.pathParam("id");
                MessageDigest.getInstance("SHA1").digest("hash1".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash2".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash3".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash4".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash5".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash6".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash7".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash8".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash9".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash10".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash11".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash12".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash13".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash14".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash15".getBytes(StandardCharsets.UTF_8));
                ctx.response().end("ok");
            } catch (Exception e) {
                ctx.response().setStatusCode(500).end(e.getMessage());
            }
        });

        // GET /iast/sampling-by-route-method-count-2/:id
        router.get("/iast/sampling-by-route-method-count-2/:id").handler(ctx -> {
            try {
                String id = ctx.pathParam("id");
                MessageDigest.getInstance("SHA1").digest("hash1".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash2".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash3".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash4".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash5".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash6".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash7".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash8".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash9".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash10".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash11".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash12".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash13".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash14".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash15".getBytes(StandardCharsets.UTF_8));
                ctx.response().end("ok");
            } catch (Exception e) {
                ctx.response().setStatusCode(500).end(e.getMessage());
            }
        });

        // POST /iast/sampling-by-route-method-count/:id
        router.post("/iast/sampling-by-route-method-count/:id").handler(ctx -> {
            try {
                String id = ctx.pathParam("id");
                MessageDigest.getInstance("SHA1").digest("hash1".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash2".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash3".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash4".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash5".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash6".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash7".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash8".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash9".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash10".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash11".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash12".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash13".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash14".getBytes(StandardCharsets.UTF_8));
                MessageDigest.getInstance("SHA1").digest("hash15".getBytes(StandardCharsets.UTF_8));
                ctx.response().end("ok");
            } catch (Exception e) {
                ctx.response().setStatusCode(500).end(e.getMessage());
            }
        });
    }
}