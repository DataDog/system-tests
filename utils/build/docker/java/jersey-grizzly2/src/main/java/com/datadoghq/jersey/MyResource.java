package com.datadoghq.jersey;

import io.opentracing.Scope;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import jakarta.json.JsonValue;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.PathSegment;
import jakarta.xml.bind.annotation.XmlAttribute;
import jakarta.xml.bind.annotation.XmlRootElement;
import jakarta.xml.bind.annotation.XmlValue;

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
    @Path("/waf/{params: .*}")
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


    @XmlRootElement(name = "a")
    public static class XmlObject {
        @XmlValue
        public String value;

        @XmlAttribute
        public String attack;

        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder("AElement{");
            sb.append("value='").append(value).append('\'');
            sb.append(", attack='").append(attack).append('\'');
            sb.append('}');
            return sb.toString();
        }
    }
}
