package com.datadoghq.jersey;

import com.datadoghq.system_tests.iast.utils.*;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import jakarta.json.JsonValue;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.PathSegment;
import jakarta.ws.rs.core.Response;
import jakarta.xml.bind.annotation.XmlAttribute;
import jakarta.xml.bind.annotation.XmlRootElement;
import jakarta.xml.bind.annotation.XmlValue;

import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.util.Collection;
import java.util.HashMap;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.List;
import java.util.function.Function;
import java.util.function.Predicate;
import javax.crypto.BadPaddingException;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import javax.naming.NamingException;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.Cookie;

import static com.datadoghq.jersey.Main.DATA_SOURCE;
import static com.datadoghq.jersey.Main.LDAP_CONTEXT;


@SuppressWarnings("Convert2MethodRef")
@Path("/")
@Produces(MediaType.TEXT_PLAIN)
public class MyResource {
    String superSecretAccessKey = "insecure";

    private final CryptoExamples crypto = new CryptoExamples();
    private final SqlExamples sql = new SqlExamples(DATA_SOURCE) ;
    private final LDAPExamples ldap = new LDAPExamples(LDAP_CONTEXT);
    private final CmdExamples cmd = new CmdExamples();
    private final PathExamples path = new PathExamples();

    @GET
    public String hello() {
        var tracer = GlobalTracer.get();
        Span span = tracer.buildSpan("test-span").start();
        span.setTag("test-tag", "my value");
        try {
            return "Hello World!";
        } finally {
            span.finish();
        }
    }

    @GET
    @Path("/headers")
    public Response headers() {
        return Response.status(200)
                .header("content-type", "text/plain")
                .header("content-length", "42")
                .header("content-language", "en-US")
                .entity("012345678901234567890123456789012345678901").build();
    }

    @GET
    @Path("/params/{params: .*}")
    public String waf(@PathParam("params") List<PathSegment> params) {
        return params.toString();
    }

    @POST
    @Path("/waf")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String postWafUrlencoded(MultivaluedMap<String, String> form) {
        return form.toString();
    }

    @POST
    @Path("/waf")
    @Consumes(MediaType.APPLICATION_JSON)
    public String postWafJson(JsonValue node) {
        return node.toString();
    }

    @POST
    @Path("/waf")
    @Consumes(MediaType.APPLICATION_XML)
    public String postWafXml(XmlObject object) {
        return object.toString();
    }

    @GET
    @Path("/status")
    public Response status(@QueryParam("code") Integer code) {
        return Response.status(code).build();
    }

    private static final Map<String, String> METADATA = createMetadata();
    private static final Map<String, String> createMetadata() {
        HashMap<String, String> h = new HashMap<>();
        h.put("metadata0", "value0");
        h.put("metadata1", "value1");
        return h;
    }

    @GET
    @Path("/user_login_success_event")
    public String userLoginSuccess(@DefaultValue("system_tests_user") @QueryParam("event_user_id") String userId) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackLoginSuccessEvent(userId, METADATA);

        return "ok";
    }

    @GET
    @Path("/user_login_failure_event")
    public String userLoginFailure(@DefaultValue("system_tests_user") @QueryParam("event_user_id") String userId,
                                   @DefaultValue("true") @QueryParam("event_user_exists") boolean eventUserExists) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackLoginFailureEvent(userId, eventUserExists, METADATA);

        return "ok";
    }

    @GET
    @Path("/custom_event")
    public String customEvent(@DefaultValue("system_tests_event") @QueryParam("event_name") String eventName) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackCustomEvent(eventName, METADATA);

        return "ok";
    }

    @XmlRootElement(name = "string")
    public static class XmlObject {
        @XmlValue
        public String value;

        @XmlAttribute
        public String attack;

        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder("StringElement{");
            sb.append("value='").append(value).append('\'');
            sb.append(", attack='").append(attack).append('\'');
            sb.append('}');
            return sb.toString();
        }
    }

    @GET
    @Path("/make_distant_call")
    DistantCallResponse make_distant_call(@QueryParam("url") String url) throws Exception {
        URL urlObject = new URL(url);

        HttpURLConnection con = (HttpURLConnection) urlObject.openConnection();
        con.setRequestMethod("GET");

        // Save request headers
        HashMap<String, String> request_headers = new HashMap<String, String>();
        for (Map.Entry<String, List<String>> header: con.getRequestProperties().entrySet()) {
            if (header.getKey() == null) {
                continue;
            }

            request_headers.put(header.getKey(), header.getValue().get(0));
        }

        // Save response headers and status code
        int status_code = con.getResponseCode();
        HashMap<String, String> response_headers = new HashMap<String, String>();
        for (Map.Entry<String, List<String>> header: con.getHeaderFields().entrySet()) {
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

        return result;
    }

    public static final class DistantCallResponse {
        public String url;
        public int status_code;
        public HashMap<String, String> request_headers;
        public HashMap<String, String> response_headers;
    }

    @GET
    @Path("/iast/insecure_hashing/deduplicate")
    public String removeDuplicates() throws NoSuchAlgorithmException {
        return crypto.removeDuplicates(superSecretAccessKey);
    }

    @GET
    @Path("/iast/insecure_hashing/multiple_hash")
    public String multipleInsecureHash() throws NoSuchAlgorithmException {
        return crypto.multipleInsecureHash(superSecretAccessKey);
    }

    @GET
    @Path("/iast/insecure_hashing/test_secure_algorithm")
    public String secureHashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.secureHashing(superSecretAccessKey);
    }

    @GET
    @Path("/iast/insecure_hashing/test_md5_algorithm")
    public String insecureMd5Hashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.insecureMd5Hashing(superSecretAccessKey);
    }

    @GET
    @Path("/iast/insecure_cipher/test_secure_algorithm")
    public String secureCipher() throws NoSuchAlgorithmException, NoSuchPaddingException,
        IllegalBlockSizeException, BadPaddingException, InvalidKeyException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.secureCipher(superSecretAccessKey);
    }

    @GET
    @Path("/iast/insecure_cipher/test_insecure_algorithm")
    public String insecureCipher() throws NoSuchAlgorithmException, NoSuchPaddingException,
        IllegalBlockSizeException, BadPaddingException, InvalidKeyException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return crypto.insecureCipher(superSecretAccessKey);
    }

    @POST
    @Path("/iast/sqli/test_insecure")
    public Object insecureSql(@FormParam("username") String username, @FormParam("password") String password) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return sql.insecureSql(username, password);
    }

    @POST
    @Path("/iast/sqli/test_secure")
    public Object secureSql(@FormParam("username") String username, @FormParam("password") String password) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return sql.secureSql(username, password);
    }

    @POST
    @Path("/iast/cmdi/test_insecure")
    public String insecureCmd(@FormParam("cmd") final String cmd) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return this.cmd.insecureCmd(cmd);
    }

    @POST
    @Path("/iast/ldapi/test_insecure")
    public String insecureLDAP(@FormParam("username") final String username, @FormParam("password") final String password) throws NamingException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return ldap.injection(username, password);
    }

    @POST
    @Path("/iast/ldapi/test_secure")
    public String secureLDAP() throws NamingException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return ldap.secure();
    }

    @POST
    @Path("/iast/path_traversal/test_insecure")
    public String insecurePathTraversal(@FormParam("path") final String path) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return this.path.insecurePathTraversal(path);
    }

    @POST
    @Path("/iast/source/parameter/test")
    public String sourceParameter(@FormParam("table") final String source) {
        sql.insecureSql(source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", source);
    }

    @GET
    @Path("/iast/source/header/test")
    public String sourceHeaders(@HeaderParam("table") String header) {
        sql.insecureSql(header, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", header);
    }

    @GET
    @Path("/iast/source/cookievalue/test")
    public String sourceCookieValue(@CookieParam("table") final String value) {
        sql.insecureSql(value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", value);
    }

    @GET
    @Path("/iast/source/cookiename/test")
    public String sourceCookieName(@Context final HttpHeaders headers) {
        Collection<Cookie> cookies = headers.getCookies().values();
        final String table = find(cookies, c -> c.getName().equalsIgnoreCase("user"), Cookie::getName);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", cookies);
    }

    @POST
    @Path("/iast/source/body/test")
    public String sourceBody(TestBean testBean) {
        System.out.println("Inside body test testbean: " + testBean);
        String value = testBean.getValue();
        sql.insecureSql(value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("@RequestBody to Test bean -> value:%", value);
    }

    @SuppressWarnings("OptionalGetWithoutIsPresent")
    private <E> String find(final Collection<E> list,
                            final Predicate<E> matcher,
                            final Function<E, String> provider) {
        return provider.apply(list.stream().filter(matcher).findFirst().get());
    }
}
