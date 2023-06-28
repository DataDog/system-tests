package com.datadoghq.jersey;

import com.datadoghq.system_tests.iast.utils.CmdExamples;
import com.datadoghq.system_tests.iast.utils.CryptoExamples;
import com.datadoghq.system_tests.iast.utils.LDAPExamples;
import com.datadoghq.system_tests.iast.utils.PathExamples;
import com.datadoghq.system_tests.iast.utils.SqlExamples;
import com.datadoghq.system_tests.iast.utils.SsrfExamples;
import com.datadoghq.system_tests.iast.utils.WeakRandomnessExamples;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import static com.datadoghq.jersey.Main.DATA_SOURCE;
import static com.datadoghq.jersey.Main.LDAP_CONTEXT;

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

    @GET
    @Path("/insecure-cookie/test_empty_cookie")
    public Response insecureCookieEmptyCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "").build();
    }
    @GET
    @Path("/insecure-cookie/test_insecure")
    public Response  insecureCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;HttpOnly=true;SameSite=Strict").build();
    }

    @GET
    @Path("/insecure-cookie/test_secure")
    public Response  secureCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;HttpOnly=true;SameSite=Strict").build();
    }

    @GET
    @Path("/no-samesite-cookie/test_insecure")
    public Response  noSameSiteCookieInsecure() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;HttpOnly=true;Secure").build();
    }

    @GET
    @Path("/no-samesite-cookie/test_empty_cookie")
    public Response  noSameSiteCookieEmptyCookie() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "").build();
    }

    @GET
    @Path("/no-samesite-cookie/test_secure")
    public Response  noSameSiteCookieSecure() {
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;HttpOnly=true;SameSite=Strict").build();
    }

    @GET
    @Path("/no-httponly-cookie-cookie/test_empty_cookie")
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
        return Response.status(Response.Status.OK).header("Set-Cookie", "user-id=7;Secure;HttpOnly=true;SameSite=Strict").build();
    }

}
