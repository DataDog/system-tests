package com.datadoghq.resteasy;

import com.datadoghq.system_tests.iast.utils.*;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import datadog.appsec.api.blocking.Blocking;
import datadog.appsec.api.login.EventTrackerV2;
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

import static datadog.appsec.api.user.User.setUser;
import static java.util.Collections.emptyMap;

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
        library.put("name", "java");
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

    /**
     * Endpoint for sending a response with five custom headers.
     */
    @GET
    @Path("/customResponseHeaders")
    @Produces(MediaType.TEXT_PLAIN)
    public Response customResponseHeaders() {
        return Response.status(200)
                .header("Content-Language", "en-US")
                .header("X-Test-Header-1", "value1")
                .header("X-Test-Header-2", "value2")
                .header("X-Test-Header-3", "value3")
                .header("X-Test-Header-4", "value4")
                .header("X-Test-Header-5", "value5")
                .entity("Response with custom headers").build();
    }

    /**
     * Endpoint for sending a response with more than fifty headers.
     */
    @GET
    @Path("/exceedResponseHeaders")
    @Produces(MediaType.TEXT_PLAIN)
    public Response exceedResponseHeaders() {
        Response.ResponseBuilder builder = Response.status(200);
        for (int i = 1; i <= 50; i++) {
            builder.header("X-Test-Header-" + i, "value" + i);
        }
        builder.header("Content-Language", "en-US");
        return builder
                .entity("Response with more than 50 headers").build();
    }

    @GET
    @Path("/tag_value/{tag_value}/{status_code}")
    public Response tagValue(@PathParam("tag_value") String value, @PathParam("status_code") int code, @QueryParam("X-option") String xOption) {
        return handleTagValue(value, code, xOption, null);
    }

    @OPTIONS
    @Path("/tag_value/{tag_value}/{status_code}")
    public Response tagValueOptions(@PathParam("tag_value") String value, @PathParam("status_code") int code, @QueryParam("X-option") String xOption) {
        return handleTagValue(value, code, xOption, null);
    }

    @POST
    @Path("/tag_value/{tag_value}/{status_code}")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public Response tagValuePostForm(@PathParam("tag_value") String value, @PathParam("status_code") int code, @QueryParam("X-option") String xOption, MultivaluedMap<String, String> form) {
        ObjectNode body = null;
        if (form != null) {
            final ObjectMapper mapper = new ObjectMapper();
            body = mapper.createObjectNode();
            for (final String key : form.keySet()) {
                final ArrayNode payloadValue = mapper.createArrayNode();
                for (final String formValue : form.get(key)) {
                    payloadValue.add(formValue);
                }
                body.put(key, payloadValue);
            }
        }
        return handleTagValue(value, code, xOption, body);
    }

    @POST
    @Path("/tag_value/{tag_value}/{status_code}")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response tagValuePostJson(@PathParam("tag_value") String value, @PathParam("status_code") int code, @QueryParam("X-option") String xOption, JsonNode body) {
        return handleTagValue(value, code, xOption, body);
    }

    private Response handleTagValue(final String value, final int code, final String xOption, final JsonNode body) {
            setRootSpanTag("appsec.events.system_tests_appsec_event.value", value);
        Response.ResponseBuilder response = Response.status(code);
        if (xOption != null) {
            response = response.header("X-option", xOption);
        }
        if (value.startsWith("payload_in_response_body")) {
            final ObjectNode responseBody = new ObjectMapper().createObjectNode();
            responseBody.put("payload", body);
            response = response
                    .entity(responseBody)
                    .header("Content-Type", "application/json");
        } else {
            response = response
                    .entity("Value tagged")
                    .header("Content-Type", "text/plain");
        }
        return response.build();
    }

    @GET
    @Path("/sample_rate_route/{i}")
    public Response sampleRateRoute(@PathParam("i") int i) {
        return Response.status(200)
                .header("content-type", "text/plain")
                .entity("OK\n").build();
    }

    @GET
    @Path("/api_security/sampling/{i}")
    public Response apiSecuritySamplingWithStatus(@PathParam("i") int i) {
        return Response.status(i)
                .header("content-type", "text/plain")
                .entity("Hello!\n").build();
    }

    @GET
    @Path("/api_security_sampling/{i}")
    public Response apiSecuritySampling(@PathParam("i") int i) {
        return Response.status(200)
                .header("content-type", "text/plain")
                .entity("Hello!\n").build();
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
    @Path("/identify")
    public String identify() {
        final Map<String, String> metadata = new HashMap<>();
        metadata.put("email", "usr.email");
        metadata.put("name", "usr.name");
        metadata.put("session_id", "usr.session_id");
        metadata.put("role", "usr.role");
        metadata.put("scope", "usr.scope");
        setUser("usr.id", metadata);
        return "OK";
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

    @POST
    @Path("/user_login_success_event_v2")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces({MediaType.TEXT_HTML, MediaType.TEXT_PLAIN})
    public String userLoginSuccessV2(final UserEventRequest request) {
        EventTrackerV2.trackUserLoginSuccess(request.getLogin(), request.getUserId(), request.getMetadata());
        return "ok";
    }

    @POST
    @Path("/user_login_failure_event_v2")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces({MediaType.TEXT_HTML, MediaType.TEXT_PLAIN})
    public String userLoginFailureV2(final UserEventRequest request) {
        EventTrackerV2.trackUserLoginFailure(request.getLogin(), request.getExists(), request.getMetadata());
        return "ok";
    }

    public static class UserEventRequest {
        private String login;
        @JsonProperty("user_id")
        private String userId;  // Optional for failure event
        private boolean exists; // Optional for success event
        private Map<String, String> metadata;

        // Getters and Setters
        public String getLogin() {
            return login;
        }

        public void setLogin(String login) {
            this.login = login;
        }

        public String getUserId() {
            return userId;
        }

        public void setUserId(String userId) {
            this.userId = userId;
        }

        public boolean getExists() {
            return exists;
        }

        public void setExists(boolean exists) {
            this.exists = exists;
        }

        public Map<String, String> getMetadata() {
            return metadata;
        }

        public void setMetadata(Map<String, String> metadata) {
            this.metadata = metadata;
        }
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
