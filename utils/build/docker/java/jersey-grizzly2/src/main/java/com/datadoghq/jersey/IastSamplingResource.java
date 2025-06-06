package com.datadoghq.jersey;

import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

@Path("/iast")
public class IastSamplingResource {
    @GET
    @Path("/sampling-by-route-method-count/{id}")
    @Produces(MediaType.TEXT_PLAIN)
    public String getSamplingByRouteMethodCount(@PathParam("id") String id) {
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
            return "ok";
        } catch (Exception e) {
            throw new WebApplicationException(e.getMessage(), 500);
        }
    }

    @POST
    @Path("/sampling-by-route-method-count/{id}")
    @Produces(MediaType.TEXT_PLAIN)
    public String postSamplingByRouteMethodCount(@PathParam("id") String id) {
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
            return "ok";
        } catch (Exception e) {
            throw new WebApplicationException(e.getMessage(), 500);
        }
    }

    @GET
    @Path("/sampling-by-route-method-count-2/{id}")
    @Produces(MediaType.TEXT_PLAIN)
    public String getSamplingByRouteMethodCount2(@PathParam("id") String id) {
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
            return "ok";
        } catch (Exception e) {
            throw new WebApplicationException(e.getMessage(), 500);
        }
    }
} 