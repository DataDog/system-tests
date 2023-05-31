package com.datadoghq.jersey;

import com.datadoghq.system_tests.iast.utils.SqlExamples;
import com.datadoghq.system_tests.iast.utils.TestBean;

import jakarta.ws.rs.*;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.Cookie;
import jakarta.ws.rs.core.HttpHeaders;
import java.util.Collection;
import java.util.function.Function;
import java.util.function.Predicate;

import static com.datadoghq.jersey.Main.DATA_SOURCE;

@SuppressWarnings("Convert2MethodRef")
@Path("/iast/source")
public class IastSourceResource {

    private final SqlExamples sql = new SqlExamples(DATA_SOURCE) ;

    @POST
    @Path("/parameter/test")
    public String sourceParameter(@FormParam("table") final String source) {
        sql.insecureSql(source, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Parameters => source: %s", source);
    }

    @GET
    @Path("/header/test")
    public String sourceHeaders(@HeaderParam("table") String header) {
        sql.insecureSql(header, (statement, sql) -> statement.executeQuery(sql));
        return String.format("Request Headers => %s", header);
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
        final String table = find(cookies, c -> c.getName().equalsIgnoreCase("user"), Cookie::getName);
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
}
