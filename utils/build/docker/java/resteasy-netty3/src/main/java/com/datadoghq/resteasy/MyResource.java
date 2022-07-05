package com.datadoghq.resteasy;


import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import javax.ws.rs.*;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.MultivaluedMap;
import javax.ws.rs.core.PathSegment;
import javax.ws.rs.core.Response;
import javax.xml.bind.annotation.XmlAttribute;
import javax.xml.bind.annotation.XmlRootElement;
import javax.xml.bind.annotation.XmlValue;
import java.util.List;

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
    public String postWafJson(Object node) {
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
}
