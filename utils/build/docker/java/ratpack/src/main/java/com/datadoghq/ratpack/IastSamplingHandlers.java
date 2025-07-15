package com.datadoghq.ratpack;

import ratpack.handling.Context;
import ratpack.handling.Handler;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

public class IastSamplingHandlers {
    public static Handler getSamplingByRouteMethodCount() {
        return ctx -> {
            try {
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
                ctx.getResponse().send("ok");
            } catch (Exception e) {
                ctx.getResponse().status(500).send(e.getMessage());
            }
        };
    }

    public static Handler postSamplingByRouteMethodCount() {
        return ctx -> {
            try {
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
                ctx.getResponse().send("ok");
            } catch (Exception e) {
                ctx.getResponse().status(500).send(e.getMessage());
            }
        };
    }

    public static Handler getSamplingByRouteMethodCount2() {
        return ctx -> {
            try {
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
                ctx.getResponse().send("ok");
            } catch (Exception e) {
                ctx.getResponse().status(500).send(e.getMessage());
            }
        };
    }
}