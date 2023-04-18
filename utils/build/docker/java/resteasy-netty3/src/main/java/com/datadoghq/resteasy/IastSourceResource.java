package com.datadoghq.resteasy;

import com.datadoghq.system_tests.iast.utils.SqlExamples;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import com.datadoghq.system_tests.iast.utils.TestBean;

import javax.ws.rs.*;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.Cookie;
import javax.ws.rs.core.HttpHeaders;
import java.util.Map;

import static com.datadoghq.resteasy.Main.DATA_SOURCE;

@Path("/iast/source")
public class IastSourceResource {

    private final SqlExamples sql = new SqlExamples(DATA_SOURCE) ;

    @POST
    @Path("/parameter/test")
    public String sourceParameter(@FormParam("source") final String source) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        sql.insecureSql(source, source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", source);
    }

    @GET
    @Path("/header/test")
    public String sourceHeaders(@HeaderParam("random-key") String header) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        sql.insecureSql(header, header, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", header);
    }

    @GET
    @Path("/cookievalue/test")
    public String sourceCookieValue(@CookieParam("cookie-source-name") final String value) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        sql.insecureSql(value, value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", value);
    }

    @GET
    @Path("/cookiename/test")
    public String sourceCookieName(@Context final HttpHeaders headers) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        Map<String, Cookie> cookies = headers.getCookies();
        for (Cookie cookie : cookies.values()) {
            String name = cookie.getName();
            sql.insecureSql(name, name, (statement, sql) -> statement.executeQuery(sql));
            break;
        }
        return String.format("Request Cookies => %s", cookies);
    }

    @POST
    @Path("/body/test")
    public String sourceBody(TestBean testBean) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        System.out.println("Inside body test testbean: " + testBean);
        String name = testBean.getName();
        String value = testBean.getValue();
        sql.insecureSql(name, value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("@RequestBody to Test bean -> name: %s, value:%s", name, value);
    }
}
