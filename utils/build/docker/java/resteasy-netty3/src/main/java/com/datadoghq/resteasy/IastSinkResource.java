package com.datadoghq.resteasy;

import com.datadoghq.system_tests.iast.utils.*;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import javax.ws.rs.*;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

import static com.datadoghq.resteasy.Main.DATA_SOURCE;
import static com.datadoghq.resteasy.Main.LDAP_CONTEXT;

import java.net.URI;
import java.net.URISyntaxException;

@Path("/iast")
@Produces(MediaType.TEXT_PLAIN)
public class IastSinkResource {

    private final String superSecretAccessKey = "insecure";
    private final CryptoExamples crypto = new CryptoExamples();
    private final SqlExamples sql = new SqlExamples(DATA_SOURCE) ;
    private final LDAPExamples ldap = new LDAPExamples(LDAP_CONTEXT);
    private final CmdExamples cmd = new CmdExamples();
    private final PathExamples path = new PathExamples();
    private final SsrfExamples ssrf = new SsrfExamples();
    private final WeakRandomnessExamples weakRandomness = new WeakRandomnessExamples();
    private final XPathExamples xPathExamples = new XPathExamples();
    private final ReflectionExamples reflectionExamples = new ReflectionExamples();

    @GET
    @Path("/insecure_hashing/deduplicate")
    public String removeDuplicates() {
        return crypto.removeDuplicates(superSecretAccessKey);
    }

    @GET
    @Path("/insecure_hashing/multiple_hash")
    public String multipleInsecureHash() {
        return crypto.multipleInsecureHash(superSecretAccessKey);
    }

    @GET
    @Path("/insecure_hashing/test_secure_algorithm")
    public String secureHashing() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.secureHashing(superSecretAccessKey);
    }

    @GET
    @Path("/insecure_hashing/test_md5_algorithm")
    public String insecureMd5Hashing() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.insecureMd5Hashing(superSecretAccessKey);
    }


    @GET
    @Path("/insecure_cipher/test_secure_algorithm")
    public String secureCipher() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.secureCipher(superSecretAccessKey);
    }

    @GET
    @Path("/insecure_cipher/test_insecure_algorithm")
    public String insecureCipher() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.insecureCipher(superSecretAccessKey);
    }

    @POST
    @Path("/sqli/test_insecure")
    public Object insecureSql(@FormParam("username") String username, @FormParam("password") String password) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return sql.insecureSql(username, password);
    }

    @POST
    @Path("/sqli/test_secure")
    public Object secureSql(@FormParam("username") String username, @FormParam("password") String password) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return sql.secureSql(username, password);
    }

    @POST
    @Path("/cmdi/test_insecure")
    public String insecureCmd(@FormParam("cmd") final String cmd) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return this.cmd.insecureCmd(cmd);
    }

    @POST
    @Path("/ldapi/test_insecure")
    public String insecureLDAP(@FormParam("username") final String username, @FormParam("password") final String password) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return ldap.injection(username, password);
    }

    @POST
    @Path("/ldapi/test_secure")
    public String secureLDAP() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return ldap.secure();
    }

    @POST
    @Path("/path_traversal/test_insecure")
    public String insecurePathTraversal(@FormParam("path") final String path) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return this.path.insecurePathTraversal(path);
    }

    @POST
    @Path("/ssrf/test_insecure")
    public String insecureSsrf(@FormParam("url") final String url) {
        return this.ssrf.insecureUrl(url);
    }

    @GET
    @Path("/weak_randomness/test_insecure")
    public String weakRandom() {
        return this.weakRandomness.weakRandom();
    }

    @GET
    @Path("/weak_randomness/test_secure")
    public String secureRandom() {
        return this.weakRandomness.secureRandom();
    }

    @GET
    @Path("/unvalidated_redirect/test_secure_header")
    public Response secureUnvalidatedRedirectHeader() {
        return Response.status(Response.Status.TEMPORARY_REDIRECT).header("Location", "http://dummy.location.com").build();
    }

    @POST
    @Path("/unvalidated_redirect/test_insecure_header")
    public Response insecureUnvalidatedRedirectHeader(@FormParam("location") final String location) {
        return Response.status(Response.Status.TEMPORARY_REDIRECT).header("Location", location).build();
    }

    @GET
    @Path("/unvalidated_redirect/test_secure_redirect")
    public Response secureUnvalidatedRedirect() throws URISyntaxException {
        return Response.status(Response.Status.TEMPORARY_REDIRECT).location(new URI("http://dummy.location.com")).build();
    }

    @POST
    @Path("/unvalidated_redirect/test_insecure_redirect")
    public Response insecureUnvalidatedRedirect(@FormParam("location") final String location) throws URISyntaxException {
        return Response.status(Response.Status.TEMPORARY_REDIRECT).location(new URI(location)).build();
    }

    @POST
    @Path("/xpathi/test_secure")
    public String secureXPath() {
        xPathExamples.secureXPath();
        return "Secure";
    }

    @POST
    @Path("/xpathi/test_insecure")
    public String insecureXPath(@FormParam("expression") final String expression) {
        xPathExamples.insecureXPath(expression);
        return "Insecure";
    }

    @GET
    @Path("/insecure-cookie/test_empty_cookie")
    public Response insecureCookieEmptyCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "").build();
    }

    @GET
    @Path("/insecure-cookie/test_insecure")
    public Response  insecureCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;HttpOnly;SameSite=Strict").build();
    }

    @GET
    @Path("/insecure-cookie/test_secure")
    public Response  secureCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict").build();
    }

    @GET
    @Path("/no-samesite-cookie/test_insecure")
    public Response  noSameSiteCookieInsecure() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;HttpOnly;Secure").build();
    }

    @GET
    @Path("/no-samesite-cookie/test_empty_cookie")
    public Response  noSameSiteCookieEmptyCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "").build();
    }

    @GET
    @Path("/no-samesite-cookie/test_secure")
    public Response  noSameSiteCookieSecure() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict").build();
    }

    @GET
    @Path("/no-httponly-cookie/test_empty_cookie")
    public Response  noHttpOnlyCookieEmptyCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "").build();
    }
    @GET
    @Path("/no-httponly-cookie/test_insecure")
    public Response  noHttpOnlyCookieInsecure() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;SameSite=Strict").build();
    }

    @GET
    @Path("/no-httponly-cookie/test_secure")
    public Response  noHttpOnlyCookieSecure() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict").build();
    }

    @GET
    @Path("/insecure-auth-protocol/test")
    public Response  insecureAuthProtocol() {
        return Response.status(Response.Status.OK).build();
    }

    @POST
    @Path("/reflection_injection/test_secure")
    public String secureReflection() {
        reflectionExamples.secureClassForName();
        return "Secure";
    }

    @POST
    @Path("/reflection_injection/test_insecure")
    public String insecureReflection(@FormParam("param") final String className) {
        reflectionExamples.insecureClassForName(className);
        return "Insecure";
    }

    @POST
    @Path("/sc/s/configured")
    public String scSanitizeConfigured(@FormParam("param") String param){
        String sanitized = SecurityControlUtil.sanitize(param);
        cmd.insecureCmd(sanitized);
        return "ok";
    }

    @POST
    @Path("/sc/s/not-configured")
    public Object scSanitizeSqli(@FormParam("param") String param){
        String sanitized = SecurityControlUtil.sanitize(param);
        return sql.insecureSql(sanitized, "password");
    }

    @POST
    @Path("/sc/s/all")
    public Object scSanitizeForAllVulns(@FormParam("param") String param){
        String sanitized = SecurityControlUtil.sanitizeForAllVulns(param);
        return sql.insecureSql(sanitized, "password");
    }

    @POST
    @Path("/sc/iv/configured")
    public String scValidateXSS(@FormParam("param") String param){
        if (SecurityControlUtil.validate(param)) {
            cmd.insecureCmd(param);
        }
        return "ok";
    }

    @POST
    @Path("/sc/iv/not-configured")
    public String scValidateSqli(@FormParam("param") String param){
        if (SecurityControlUtil.validate(param)) {
            sql.insecureSql(param, "password");
        }
        return "ok";
    }

    @POST
    @Path("/sc/iv/all")
    public String scValidateForAllVulns(@FormParam("param") String param){
        if (SecurityControlUtil.validateForAllVulns(param)) {
            sql.insecureSql(param, "password");
        }
        return "ok";
    }

    @POST
    @Path("/sc/iv/overloaded/secure")
    public String scIVOverloadedSecure(@FormParam("user") String user, @FormParam("password") String pass){
        if (SecurityControlUtil.overloadedValidation(null, user, pass)) {
            sql.insecureSql(user, pass);
        }
        return "ok";
    }

    @POST
    @Path("/sc/iv/overloaded/insecure")
    public String scIVOverloadedInsecure(@FormParam("user") String user, @FormParam("password") String pass){
        if (SecurityControlUtil.overloadedValidation(user, pass)) {
            sql.insecureSql(user, pass);
        }
        return "ok";
    }

    @POST
    @Path("/sc/s/overloaded/secure")
    public String scSOverloadedSecure(@FormParam("param") String param){
        String sanitized = SecurityControlUtil.overloadedSanitize(param);
        cmd.insecureCmd(sanitized);
        return "ok";
    }

    @POST
    @Path("/sc/s/overloaded/insecure")
    public String scSOverloadedInsecure(@FormParam("param") String param){
        String sanitized = SecurityControlUtil.overloadedSanitize(param, null);
        cmd.insecureCmd(sanitized);
        return "ok";
    }

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
