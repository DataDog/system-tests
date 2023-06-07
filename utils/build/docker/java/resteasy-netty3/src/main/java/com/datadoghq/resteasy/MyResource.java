package com.datadoghq.resteasy;

import datadog.appsec.api.blocking.Blocking;
import datadog.trace.api.interceptor.MutableSpan;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.ws.rs.Consumes;
import javax.ws.rs.DefaultValue;
import javax.ws.rs.GET;
import javax.ws.rs.HeaderParam;
import javax.ws.rs.OPTIONS;
import javax.ws.rs.POST;
import javax.ws.rs.Path;
import javax.ws.rs.PathParam;
import javax.ws.rs.Produces;
import javax.ws.rs.QueryParam;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.MultivaluedMap;
import javax.ws.rs.core.PathSegment;
import javax.ws.rs.core.Response;
import javax.xml.bind.annotation.XmlAttribute;
import javax.xml.bind.annotation.XmlRootElement;
import javax.xml.bind.annotation.XmlValue;

@Path("/")
@Produces(MediaType.TEXT_PLAIN)
public class MyResource {
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
    @Consumes(MediaType.MULTIPART_FORM_DATA)
    public String postWafMultipart(Map<String, String> form) {
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

    @GET
    @Path("/users")
    public Response users(@QueryParam("user") String user,
                          @HeaderParam("user-agent") String userAgent) {

        // associate this span with the request
        Span span = GlobalTracer.get().activeSpan();
        span.setTag("http.request.headers.user-agent", userAgent);

        ((MutableSpan)span).getLocalRootSpan().setTag("usr.id", user);
        Blocking.forUser(user).blockIfMatch();
        return Response.status(200).entity(user).build();
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
