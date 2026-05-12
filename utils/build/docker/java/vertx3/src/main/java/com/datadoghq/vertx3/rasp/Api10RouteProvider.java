package com.datadoghq.vertx3.rasp;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.vertx.core.http.HttpServerRequest;
import io.vertx.core.json.JsonObject;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import io.vertx.ext.web.handler.BodyHandler;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.Proxy;
import java.net.URL;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

public class Api10RouteProvider implements Consumer<Router> {

    private static final Logger LOGGER = LoggerFactory.getLogger(Api10RouteProvider.class);
    private static final String INTERNAL_SERVER_URL = "http://internal_server:8089/mirror/%s%s";


    private final ObjectMapper mapper;
    private final OkHttpClient client;

    public Api10RouteProvider() {
        mapper = new ObjectMapper();
        client = new OkHttpClient.Builder().proxy(Proxy.NO_PROXY).build();
    }

    @Override
    public void accept(final Router router) {
        router.route("/external_request").handler(BodyHandler.create());
        router.route().path("/external_request")
                .blockingHandler(rc -> {
                    try {
                        final Request downstream = prepareRequest(rc);
                        final Response response = client.newCall(downstream).execute();
                        rc.response().setStatusCode(200).end(parseResponse(response).encode());
                    } catch (Throwable e) {
                        LOGGER.error("Failed to parse request", e);
                        JsonObject json = new JsonObject().put("error", e.getMessage());
                        rc.response().setStatusCode(500).end(json.encode());
                    }
                });
    }

    private Request prepareRequest(final RoutingContext rc) throws IOException {
        final HttpServerRequest request = rc.request();
        String urlExtra = "";
        int status = 200;
        final Request.Builder downstream = new Request.Builder();
        for (final String name : request.params().names()) {
            final String value = request.getParam(name);
            if ("status".equalsIgnoreCase(name)) {
                status = Integer.parseInt(value);
            } else if ("url_extra".equalsIgnoreCase(name)) {
                urlExtra = value;
            } else {
                downstream.header(name, value);
            }
        }
        downstream.url(new URL(String.format(INTERNAL_SERVER_URL, status, urlExtra)));
        RequestBody body = null;
        final String contentType = request.getHeader("Content-Type");
        if (contentType != null) {
            body = RequestBody.create(MediaType.parse(contentType), rc.getBody().getBytes());
        }
        downstream.method(request.rawMethod(), body);
        return downstream.build();
    }

    private JsonObject parseResponse(final Response response) throws IOException {
        final JsonObject result = new JsonObject();
        result.put("status", response.code());
        final ResponseBody body = response.body();
        if (response.code() >= 200 && response.code() < 300) {
            if (body != null) {
                result.put("payload", mapper.readValue(body.bytes(), Map.class));
            }
            final Map<String, Object> headers = new HashMap<>();
            for (final String header : response.headers().names()) {
                final List<String> value = response.headers(header);
                headers.put(header, value.size() == 1 ? value.get(0) : value);
            }
            result.put("headers", headers);
        } else {
            result.put("error", body != null ? body.string() : "Unknown error");
        }
        return result;
    }
}
