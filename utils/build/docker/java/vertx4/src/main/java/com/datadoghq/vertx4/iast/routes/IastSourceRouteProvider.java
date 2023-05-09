package com.datadoghq.vertx4.iast.routes;

import com.datadoghq.system_tests.iast.utils.SqlExamples;
import io.vertx.core.http.Cookie;
import io.vertx.core.http.HttpServerRequest;
import io.vertx.core.json.JsonObject;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.handler.BodyHandler;

import javax.sql.DataSource;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.function.Consumer;

public class IastSourceRouteProvider implements Consumer<Router> {

    private final DataSource dataSource;

    public IastSourceRouteProvider(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void accept(final Router router) {
        final SqlExamples sql = new SqlExamples(dataSource);

        router.route("/iast/source/*").handler(BodyHandler.create());

        router.post("/iast/source/parameter/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String source = request.getParam("source");
            sql.insecureSql(source, source, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Parameters => source: %s", source));
        });
        router.post("/iast/source/parametername/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            List<String> parameterNames = new ArrayList<>(request.params().names());
            final String source = parameterNames.get(0);
            sql.insecureSql(source, source, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Parameter Names => %s", parameterNames));
        });
        router.get("/iast/source/headername/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            List<String> headerNames = new ArrayList<>(request.headers().names());
            String headerName = headerNames.stream().filter(name -> name.equals("random-key")).findFirst().get();
            sql.insecureSql(headerName, headerName, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Headers => %s", headerNames));
        });
        router.get("/iast/source/header/test").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String header = request.getHeader("random-key");
            sql.insecureSql(header, header, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Headers => %s", header));
        });
        router.get("/iast/source/cookiename/test").handler(ctx -> {
            Cookie cookie = ctx.request().getCookie("cookie-source-name");
            String name = cookie.getName();
            sql.insecureSql(name, name, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Cookies => %s", Arrays.asList(cookie)));
        });
        router.get("/iast/source/cookievalue/test").handler(ctx -> {
            Cookie cookie = ctx.request().getCookie("cookie-source-name");
            String value = cookie.getValue();
            sql.insecureSql(value, value, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("Request Cookies => %s", Arrays.asList(cookie)));
        });
        router.post("/iast/source/body/test").handler(ctx -> {
            final JsonObject testBean = ctx.body().asJsonObject();
            String name = testBean.getString("name");
            String value = testBean.getString("value");
            sql.insecureSql(name, value, (statement, query) -> statement.executeQuery(query));
            ctx.response().end(String.format("@RequestBody to Test bean -> name: %s, value:%s", name, value));
        });
    }
}
