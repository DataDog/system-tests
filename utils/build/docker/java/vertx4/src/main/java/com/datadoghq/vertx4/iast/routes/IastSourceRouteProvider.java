package com.datadoghq.vertx4.iast.routes;

import com.datadoghq.system_tests.iast.utils.SqlExamples;
import io.vertx.core.http.Cookie;
import io.vertx.core.http.HttpServerRequest;
import io.vertx.core.json.JsonObject;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.handler.BodyHandler;

import javax.sql.DataSource;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.Predicate;

@SuppressWarnings("Convert2MethodRef")
public class IastSourceRouteProvider implements Consumer<Router> {

    private final DataSource dataSource;

    public IastSourceRouteProvider(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void accept(final Router router) {
        final SqlExamples sql = new SqlExamples(dataSource);

        router.route("/iast/source/*").handler(BodyHandler.create());

        router.get("/iast/source/parameter/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String table = request.getParam("table");
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Parameters => source: %s", table));
        });
        router.post("/iast/source/parameter/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String table = request.getParam("table");
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Parameters => source: %s", table));
        });
        router.get("/iast/source/parametername/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            List<String> parameterNames = new ArrayList<>(request.params().names());
            final String table = parameterNames.get(0);
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Parameter Names => %s", parameterNames));
        });
        router.post("/iast/source/parametername/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            List<String> parameterNames = new ArrayList<>(request.params().names());
            final String table = parameterNames.get(0);
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Parameter Names => %s", parameterNames));
        });
        router.get("/iast/source/headername/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            List<String> headerNames = new ArrayList<>(request.headers().names());
            final String table = find(headerNames, header -> header.equalsIgnoreCase("user"));
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Headers => %s", headerNames));
        });
        router.get("/iast/source/header/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String table = request.getHeader("table");
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Headers => %s", table));
        });
        router.get("/iast/source/cookiename/test").handler(ctx -> {
            Cookie cookie = ctx.request().getCookie("table");
            String table = cookie.getName();
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Cookies => %s", cookie));
        });
        router.get("/iast/source/cookievalue/test").handler(ctx -> {
            Cookie cookie = ctx.request().getCookie("table");
            String table = cookie.getValue();
            sql.insecureSql(table, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Cookies => %s", cookie));
        });
        router.post("/iast/source/body/test").handler(ctx -> {
            final JsonObject testBean = ctx.body().asJsonObject();
            String value = testBean.getString("value");
            sql.insecureSql(value, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("@RequestBody to Test bean -> value:%s", value));
        });
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
