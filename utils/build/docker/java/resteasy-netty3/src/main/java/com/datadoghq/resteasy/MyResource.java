package com.datadoghq.resteasy;

import com.datadoghq.system_tests.iast.utils.*;

import datadog.appsec.api.blocking.Blocking;
import datadog.trace.api.interceptor.MutableSpan;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import javax.ws.rs.*;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.MultivaluedMap;
import javax.ws.rs.core.PathSegment;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.HttpHeaders;
import javax.xml.bind.annotation.XmlAttribute;
import javax.xml.bind.annotation.XmlRootElement;
import javax.xml.bind.annotation.XmlValue;

import java.util.HashMap;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.List;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

import com.fasterxml.jackson.databind.ObjectMapper;

import com.datadoghq.system_tests.iast.utils.CryptoExamples;

@Path("/")
@Produces(MediaType.TEXT_PLAIN)
public class MyResource {

    private final CryptoExamples cryptoExamples = new CryptoExamples();

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
    @Path("/healthcheck")
    @Produces(MediaType.APPLICATION_JSON)
    public Map<String, Object> healthcheck() {
        String version;

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        getClass().getClassLoader().getResourceAsStream("dd-java-agent.version"),
                        StandardCharsets.ISO_8859_1))) {
            String line = reader.readLine();
            if (line == null) {
                throw new RuntimeException("Can't get version");
            }
            version = line;
        } catch (Exception e) {
            throw new RuntimeException("Can't get version", e);
        }

        Map<String, String> library = new HashMap<>();
        library.put("language", "java");
        library.put("version", version);

        Map<String, Object> response = new HashMap<>();
        response.put("status", "ok");
        response.put("library", library);

        return response;
    }

    @GET
    @Path("/headers")
    public Response headers() {
        return Response.status(200)
                .header("content-type", "text/plain")
                .header("content-language", "en-US")
                .entity("012345678901234567890123456789012345678901").build();
    }

    @GET
    @Path("/tag_value/{value}/{code}")
    public Response tagValue(@PathParam("value") String value, @PathParam("code") int code) {
        setRootSpanTag("appsec.events.system_tests_appsec_event.value", value);
        return Response.status(code)
                .header("content-type", "text/plain")
                .entity("Value tagged").build();
    }

    @OPTIONS
    @Path("/tag_value/{value}/{code}")
    public Response tagValueOptions(@PathParam("value") String value, @PathParam("code") int code) {
        return tagValue(value, code);
    }

    @POST
    @Path("/tag_value/{value}/{code}")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public Response tagValuePost(@PathParam("value") String value, @PathParam("code") int code, MultivaluedMap<String, String> form) {
        return tagValue(value, code);
    }

    @GET
    @Path("/params/{params: .*}")
    public String params(@PathParam("params") List<PathSegment> params) {
        return params.toString();
    }

    @GET
    @Path("/waf/{params: .*}")
    public String wafParams(@PathParam("params") List<PathSegment> params) {
        return params.toString();
    }

    @GET
    @Path("/waf")
    public String waf() {
        return "Hello world!";
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
    public String postWafJson(Object node) {
        return node.toString();
    }

    @POST
    @Path("/waf")
    @Consumes(MediaType.APPLICATION_XML)
    public String postWafXml(XmlObject object) {
        return object.toString();
    }

    @POST
    @Path("/waf")
    @Consumes(MediaType.APPLICATION_OCTET_STREAM)
    public String postWafBin(byte[] data) {
        return "Hello world!";
    }

    @POST
    @Path("/waf")
    @Consumes(MediaType.TEXT_PLAIN)
    public String postWafString(String data) {
        return data;
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
    @Path("/users")
    public String users(@QueryParam("user") String user) {
        final Span span = GlobalTracer.get().activeSpan();
        if ((span instanceof MutableSpan)) {
            MutableSpan localRootSpan = ((MutableSpan) span).getLocalRootSpan();
            localRootSpan.setTag("usr.id", user);
        }
        Blocking
                .forUser(user)
                .blockIfMatch();
        return "Hello " + user;
    }

    @GET
    @Path("/user_login_success_event")
    @Produces({MediaType.TEXT_HTML, MediaType.TEXT_PLAIN})
    public String userLoginSuccess(@DefaultValue("system_tests_user") @QueryParam("event_user_id") String userId) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackLoginSuccessEvent(userId, METADATA);

        return "ok";
    }

    @GET
    @Path("/user_login_failure_event")
    @Produces({MediaType.TEXT_HTML, MediaType.TEXT_PLAIN})
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
    public DistantCallResponse make_distant_call(@QueryParam("url") String url) throws Exception {
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

    @GET
    @Path("/requestdownstream")
    public String requestdownstream() {
        String url = "http://localhost:7777/returnheaders";
        return Utils.sendGetRequest(url);
    }

    @GET
    @Path("/vulnerablerequestdownstream")
    public String vulnerableRequestdownstream() {
        cryptoExamples.insecureMd5Hashing("password");
        String url = "http://localhost:7777/returnheaders";
        return Utils.sendGetRequest(url);
    }

    @GET
    @Path("/returnheaders")
    public String returnheaders(@Context final HttpHeaders headers) {
        Map<String, String> headerMap = new HashMap<>();
        headers.getRequestHeaders().forEach((key, value) -> headerMap.put(key, value.get(0)));
        String json = "";
        try {
            json = new ObjectMapper().writeValueAsString(headerMap);
        } catch (Exception e) {
            e.printStackTrace();
        }

        return json;
    }

    @GET
    @Path("/set_cookie")
    public Response setCookie(@QueryParam("name") String name, @QueryParam("value") String value) {
        return Response.ok().header("Set-Cookie", name + "=" + value).build();
    }

    @GET
    @Path("/createextraservice")
    public String createextraservice(@QueryParam("serviceName") String serviceName) {
        setRootSpanTag("service", serviceName);
        return "ok";
    }

    public static final class DistantCallResponse {
        public String url;
        public int status_code;
        public HashMap<String, String> request_headers;
        public HashMap<String, String> response_headers;
    }

    private void setRootSpanTag(final String key, final String value) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span instanceof MutableSpan) {
            final MutableSpan rootSpan = ((MutableSpan) span).getLocalRootSpan();
            if (rootSpan != null) {
                rootSpan.setTag(key, value);
            }
        }
    }
}
