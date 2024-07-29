package com.datadoghq.resteasy;

import com.datadoghq.system_tests.iast.utils.SqlExamples;

import com.datadoghq.system_tests.iast.utils.TestBean;

import javax.ws.rs.*;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.Cookie;
import javax.ws.rs.core.HttpHeaders;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.MultivaluedMap;
import javax.ws.rs.core.UriInfo;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.function.Predicate;
import java.util.function.Function;

import static com.datadoghq.resteasy.Main.DATA_SOURCE;

@SuppressWarnings("Convert2MethodRef")
@Path("/iast/source")
public class IastSourceResource {

    private final SqlExamples sql = new SqlExamples(DATA_SOURCE) ;

    @POST
    @Path("/parameter/test")
    public String sourceParameterPost(@FormParam("table") final String source) {
        sql.insecureSql(source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", source);
    }

    @GET
    @Path("/parameter/test")
    public String sourceParameterGet(@QueryParam("table") final String source) {
        sql.insecureSql(source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", source);
    }

    @GET
    @Path("/parametername/test")
    public String sourceParameterNameGet(@Context final UriInfo uriInfo) {
        List<String> parameterNames = new ArrayList<>(uriInfo.getQueryParameters().keySet());
        final String table = parameterNames.get(0);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameter Names => %s", parameterNames);
    }

    @POST
    @Path("/parametername/test")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String sourceParameterNamePost(MultivaluedMap<String, String> form) {
        List<String> parameterNames = new ArrayList<>(form.keySet());
        final String table = parameterNames.get(0);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameter Names => %s", parameterNames);
    }

    @GET
    @Path("/header/test")
    public String sourceHeaders(@HeaderParam("table") String header) {
        sql.insecureSql(header, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", header);
    }

    @GET
    @Path("/headername/test")
    public String sourceHeaderName(@Context final HttpHeaders headers) {
        List<String> headerNames = new ArrayList<>(headers.getRequestHeaders().keySet());
        String table = find(headerNames, header -> header.equalsIgnoreCase("user"));
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", headerNames);
    }

    @GET
    @Path("/cookievalue/test")
    public String sourceCookieValue(@CookieParam("table") final String value) {
        sql.insecureSql(value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", value);
    }

    @GET
    @Path("/cookiename/test")
    public String sourceCookieName(@Context final HttpHeaders headers) {
        Collection<Cookie> cookies = headers.getCookies().values();
        final String table = find(cookies, c -> c.getName().equalsIgnoreCase("table"), Cookie::getName);
        sql.insecureSql(table, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Cookies => %s", cookies);
    }

    @POST
    @Path("/body/test")
    public String sourceBody(TestBean testBean) {
        System.out.println("Inside body test testbean: " + testBean);
        String value = testBean.getValue();
        sql.insecureSql(value, (statement, sql) -> statement.executeQuery(sql));
        return String.format("@RequestBody to Test bean -> value:%s", value);
    }

    @SuppressWarnings("OptionalGetWithoutIsPresent")
    private <E> String find(final Collection<E> list,
                            final Predicate<E> matcher,
                            final Function<E, String> provider) {
        return provider.apply(list.stream().filter(matcher).findFirst().get());
    }

    private String find(final Collection<String> list,
                        final Predicate<String> matcher) {
        return find(list, matcher, Function.identity());
    }
}
