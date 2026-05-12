package com.datadoghq.lambda;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.*;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonSyntaxException;
import datadog.trace.api.EventTracker;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import static datadog.appsec.api.user.User.setUser;
import org.apache.hc.client5.http.classic.methods.HttpGet;
import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.classic.methods.HttpPut;
import org.apache.hc.client5.http.classic.methods.HttpUriRequestBase;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.ClassicHttpResponse;
import org.apache.hc.core5.http.io.entity.EntityUtils;
import org.apache.hc.core5.http.io.entity.StringEntity;
import org.json.JSONObject;
import org.json.XML;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Java Lambda Handler for system-tests weblog
 * Supports multiple AWS event types: API Gateway REST/HTTP, ALB, Function URL
 */
public class Handler implements RequestHandler<Object, Object> {
    private static final Logger logger = LoggerFactory.getLogger(Handler.class);
    private static final Gson gson = new Gson();
    private static final String MAGIC_SESSION_KEY = "session_id";
    private static final String TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event";
    private static final String TRACK_USER = "system_tests_user";

    private enum ResponseType { API_GATEWAY_REST, API_GATEWAY_HTTP }

    /**
     * Request context containing response type and request data
     */
    private static class RequestContext {
        final ResponseType responseType;
        final String path;
        final String method;
        final Map<String, String> queryParams;
        final Map<String, String> headers;
        final String body;
        final Map<String, String> pathParams;

        RequestContext(ResponseType responseType, String path, String method,
                      Map<String, String> queryParams, Map<String, String> headers,
                      String body, Map<String, String> pathParams) {
            this.responseType = responseType;
            this.path = path != null ? path : "/";
            this.method = method;
            this.queryParams = queryParams != null ? queryParams : Collections.emptyMap();
            this.headers = headers != null ? headers : Collections.emptyMap();
            this.body = body;
            this.pathParams = pathParams != null ? pathParams : Collections.emptyMap();
        }
    }

    @Override
    public Object handleRequest(Object input, Context context) {
        logger.info("Processing event of type: {}", input.getClass().getName());

        try {
            // Route based on event type
            if (input instanceof APIGatewayProxyRequestEvent) {
                return handleAPIGatewayRestEvent((APIGatewayProxyRequestEvent) input);
            } else if (input instanceof APIGatewayV2HTTPEvent) {
                return handleAPIGatewayHttpEvent((APIGatewayV2HTTPEvent) input);
            } else if (input instanceof ApplicationLoadBalancerRequestEvent) {
                return handleALBEvent((ApplicationLoadBalancerRequestEvent) input);
            } else if (input instanceof Map) {
                return handleMapEvent((Map<String, Object>) input);
            }
        } catch (Exception e) {
            logger.error("Error processing request", e);
            // Use default response type for errors
            RequestContext errorCtx = new RequestContext(ResponseType.API_GATEWAY_REST,
                    "/", "GET", null, null, null, null);
            return createErrorResponse(errorCtx, "Internal server error: " + e.getMessage(), 500);
        }

        logger.error("Unsupported event type: {}", input.getClass().getName());
        RequestContext errorCtx = new RequestContext(ResponseType.API_GATEWAY_REST,
                "/", "GET", null, null, null, null);
        return createErrorResponse(errorCtx, "Unsupported event type", 400);
    }

    private Object handleAPIGatewayRestEvent(APIGatewayProxyRequestEvent event) {
        RequestContext ctx = new RequestContext(
                ResponseType.API_GATEWAY_REST,
                event.getPath(),
                event.getHttpMethod(),
                event.getQueryStringParameters(),
                event.getHeaders(),
                event.getBody(),
                event.getPathParameters()
        );
        return routeRequest(ctx);
    }

    private Object handleAPIGatewayHttpEvent(APIGatewayV2HTTPEvent event) {
        String rawQueryString = event.getRawQueryString();
        Map<String, String> queryParams = rawQueryString != null ?
                parseQueryString(rawQueryString) : Collections.emptyMap();

        RequestContext ctx = new RequestContext(
                ResponseType.API_GATEWAY_HTTP,
                event.getRawPath(),
                event.getRequestContext().getHttp().getMethod(),
                queryParams,
                event.getHeaders(),
                event.getBody(),
                event.getPathParameters()
        );
        return routeRequest(ctx);
    }

    private Object handleALBEvent(ApplicationLoadBalancerRequestEvent event) {
        RequestContext ctx = new RequestContext(
                ResponseType.API_GATEWAY_REST,
                event.getPath(),
                event.getHttpMethod(),
                event.getQueryStringParameters(),
                event.getHeaders(),
                event.getBody(),
                null
        );
        return routeRequest(ctx);
    }

    private Object handleMapEvent(Map<String, Object> eventMap) {
        // Check for healthcheck
        if (eventMap.containsKey("healthcheck") && Boolean.TRUE.equals(eventMap.get("healthcheck"))) {
            logger.info("Healthcheck detected, returning version info");
            return versionInfo();
        }

        // Determine event type from structure
        if (!eventMap.containsKey("requestContext")) {
            throw new IllegalArgumentException("Unknown event structure: missing requestContext");
        }

        Object requestContext = eventMap.get("requestContext");
        if (!(requestContext instanceof Map)) {
            throw new IllegalArgumentException("Invalid requestContext type");
        }

        Map<String, Object> rc = (Map<String, Object>) requestContext;

        try {
            String json = gson.toJson(eventMap);

            if (rc.containsKey("elb")) {
                ApplicationLoadBalancerRequestEvent albEvent =
                        gson.fromJson(json, ApplicationLoadBalancerRequestEvent.class);
                return handleALBEvent(albEvent);
            } else if (rc.containsKey("http")) {
                APIGatewayV2HTTPEvent httpEvent =
                        gson.fromJson(json, APIGatewayV2HTTPEvent.class);
                return handleAPIGatewayHttpEvent(httpEvent);
            } else if (rc.containsKey("stage")) {
                APIGatewayProxyRequestEvent restEvent =
                        gson.fromJson(json, APIGatewayProxyRequestEvent.class);
                return handleAPIGatewayRestEvent(restEvent);
            }
        } catch (JsonSyntaxException e) {
            logger.error("Failed to parse event as AWS Lambda event", e);
            throw new IllegalArgumentException("Invalid event structure: " + e.getMessage());
        }

        throw new IllegalArgumentException("Unknown event type in requestContext");
    }

    private Object routeRequest(RequestContext ctx) {
        logger.info("Routing request: {} {}", ctx.method, ctx.path);

        // Add HTTP headers to the current span for request matching in tests
        Span currentSpan = GlobalTracer.get().activeSpan();
        if (currentSpan != null && !ctx.headers.isEmpty()) {
            // Add user-agent for RID matching
            String userAgent = ctx.headers.get("user-agent");
            if (userAgent == null) {
                userAgent = ctx.headers.get("User-Agent");
            }
            if (userAgent != null) {
                currentSpan.setTag("http.request.headers.user-agent", userAgent);
            }
        }

        // Route to handlers
        if (ctx.path.equals("/") || ctx.path.isEmpty()) {
            return handleRoot(ctx);
        } else if (ctx.path.equals("/headers") && "GET".equals(ctx.method)) {
            return handleHeaders(ctx);
        } else if (ctx.path.equals("/healthcheck") && "GET".equals(ctx.method)) {
            return handleHealthcheck(ctx);
        } else if (ctx.path.startsWith("/params/")) {
            return handleParams(ctx);
        } else if (ctx.path.startsWith("/waf") || ctx.path.equals("/waf/")) {
            return handleWaf(ctx);
        } else if (ctx.path.equals("/session/new") && "GET".equals(ctx.method)) {
            return handleSessionNew(ctx);
        } else if (ctx.path.startsWith("/tag_value/")) {
            return handleTagValue(ctx);
        } else if (ctx.path.equals("/user_login_success_event") && "GET".equals(ctx.method)) {
            return handleUserLoginSuccessEvent(ctx);
        } else if (ctx.path.equals("/rasp/lfi")) {
            return handleRaspLfi(ctx);
        } else if (ctx.path.equals("/rasp/ssrf")) {
            return handleRaspSsrf(ctx);
        } else if (ctx.path.equals("/rasp/sqli")) {
            return handleRaspSqli(ctx);
        } else if (ctx.path.equals("/rasp/cmdi")) {
            return handleRaspCmdi(ctx);
        } else if (ctx.path.equals("/rasp/shi")) {
            return handleRaspShi(ctx);
        } else if (ctx.path.equals("/external_request")) {
            return handleExternalRequest(ctx);
        } else if (ctx.path.equals("/users") && "GET".equals(ctx.method)) {
            return handleUsers(ctx);
        }

        return createResponse(ctx, "Not Found", 404);
    }

    // Handler methods

    private Object handleRoot(RequestContext ctx) {
        return createResponse(ctx, "Hello, World!\n", 200);
    }

    private Object handleHeaders(RequestContext ctx) {
        Map<String, String> responseHeaders = new HashMap<>();
        responseHeaders.put("Content-Language", "en-US");
        return createResponse(ctx, "OK", 200, responseHeaders);
    }

    private Object handleHealthcheck(RequestContext ctx) {
        return createJsonResponse(ctx, versionInfo(), 200);
    }

    private Object handleParams(RequestContext ctx) { return createResponse(ctx, "Hello, World!\n", 200); }

    private Object handleWaf(RequestContext ctx) { return createResponse(ctx, "Hello, World!\n", 200); }

    private Object handleSessionNew(RequestContext ctx) {
        Map<String, String> cookies = new HashMap<>();
        cookies.put("session_id", MAGIC_SESSION_KEY);
        return createResponseWithCookies(ctx, MAGIC_SESSION_KEY, 200, null, cookies);
    }

    private Object handleTagValue(RequestContext ctx) {
        String[] parts = ctx.path.split("/");
        if (parts.length < 4) {
            return createResponse(ctx, "Invalid path", 400);
        }

        String tagValue = parts[2];
        int statusCode;
        try {
            statusCode = Integer.parseInt(parts[3]);
        } catch (NumberFormatException e) {
            statusCode = 200;
        }

        // Track custom AppSec event
        trackCustomEvent(tagValue);

        return createResponse(ctx, "Value tagged", statusCode);
    }

    private Object handleUserLoginSuccessEvent(RequestContext ctx) {
        trackUserLoginSuccessEvent();
        return createResponse(ctx, "OK", 200);
    }

    private Object handleRaspLfi(RequestContext ctx) {
        String file = retrieveArg("file", ctx.method, ctx.queryParams, ctx.body);
        if (file == null || file.isEmpty()) {
            return createResponse(ctx, "missing file parameter", 400);
        }

        try {
            File f = new File(file);
            long size = f.length();
            String message = "File accessed: " + file + " (" + size + " bytes)";
            return createResponse(ctx, message, 200);
        } catch (Exception e) {
            logger.debug("rasp_lfi error for file={}: {}", file, e.getClass().getSimpleName());
            String message = file + " could not be open: " + e.toString();
            return createResponse(ctx, message, 200);
        }
    }

    private Object handleRaspSsrf(RequestContext ctx) {
        String domain = retrieveArg("domain", ctx.method, ctx.queryParams, ctx.body);
        if (domain == null || domain.isEmpty()) {
            return createResponse(ctx, "missing domain parameter", 400);
        }

        String url = "http://" + domain;
        try (CloseableHttpClient client = HttpClients.createDefault()) {
            HttpGet request = new HttpGet(url);
            ClassicHttpResponse response = client.execute(request);
            String content = EntityUtils.toString(response.getEntity());
            String message = "URL accessed: " + url + " (" + content.length() + " bytes)";
            return createResponse(ctx, message, 200);
        } catch (Exception e) {
            logger.debug("rasp_ssrf error for domain={}: {}", domain, e.getClass().getSimpleName());
            String message = "url " + url + " could not be open: " + e.toString();
            return createResponse(ctx, message, 200);
        }
    }

    private Object handleRaspSqli(RequestContext ctx) {
        String userId = retrieveArg("user_id", ctx.method, ctx.queryParams, ctx.body);
        if (userId == null || userId.isEmpty()) {
            return createResponse(ctx, "missing user_id parameter", 400);
        }

        String query = "SELECT * FROM users WHERE id='" + userId + "'";

        try {
            Connection connection = DriverManager.getConnection("jdbc:sqlite::memory:");
            Statement statement = connection.createStatement();
            ResultSet results = statement.executeQuery(query);
            int count = 0;
            while (results.next()) {
                count++;
            }
            String message = "DB request with " + count + " results";
            connection.close();
            return createResponse(ctx, message, 200);
        } catch (Exception e) {
            logger.debug("rasp_sqli failure for user_id={}", userId, e);
            return createResponse(ctx, "DB request failure: " + e.toString(), 201);
        }
    }

    private Object handleRaspCmdi(RequestContext ctx) {
        String command = retrieveArg("command", ctx.method, ctx.queryParams, ctx.body);
        if (command == null || command.isEmpty()) {
            return createResponse(ctx, "missing command parameter", 400);
        }

        try {
            ProcessBuilder pb = new ProcessBuilder(command.split("\\s+"));
            Process process = pb.start();
            int exitCode = process.waitFor();
            String message = "Exec command [" + command + "] with result: " + exitCode;
            return createResponse(ctx, message, 200);
        } catch (Exception e) {
            logger.debug("rasp_cmdi failure for command={}", command, e);
            String message = "Exec command [" + command + "] failure: " + e.toString();
            return createResponse(ctx, message, 201);
        }
    }

    private Object handleRaspShi(RequestContext ctx) {
        String listDir = retrieveArg("list_dir", ctx.method, ctx.queryParams, ctx.body);
        if (listDir == null || listDir.isEmpty()) {
            return createResponse(ctx, "missing list_dir parameter", 400);
        }

        try {
            String command = "ls " + listDir;
            Process process = Runtime.getRuntime().exec(command);
            int exitCode = process.waitFor();
            String message = "Shell command [" + command + "] with result: " + exitCode;
            return createResponse(ctx, message, 200);
        } catch (Exception e) {
            logger.error("rasp_shi failure for list_dir={}", listDir, e);
            return createResponse(ctx, "Shell command failure: " + e.toString(), 201);
        }
    }

    private Object handleExternalRequest(RequestContext ctx) {
        Map<String, String> params = new HashMap<>(ctx.queryParams);
        String status = params.remove("status");
        if (status == null) {
            status = "200";
        }
        String urlExtra = params.remove("url_extra");
        if (urlExtra == null) {
            urlExtra = "";
        }

        String fullUrl = "http://internal_server:8089/mirror/" + status + urlExtra;

        try (CloseableHttpClient client = HttpClients.createDefault()) {
            HttpUriRequestBase request;
            if ("POST".equals(ctx.method)) {
                request = new HttpPost(fullUrl);
                if (ctx.body != null) {
                    ((HttpPost) request).setEntity(new StringEntity(ctx.body));
                }
            } else if ("PUT".equals(ctx.method)) {
                request = new HttpPut(fullUrl);
                if (ctx.body != null) {
                    ((HttpPut) request).setEntity(new StringEntity(ctx.body));
                }
            } else {
                request = new HttpGet(fullUrl);
            }

            // Add query params as headers
            if (ctx.body != null && !ctx.headers.isEmpty()) {
                String contentType = ctx.headers.get("content-type");
                if (contentType != null) {
                    params.put("Content-Type", contentType);
                }
            }

            for (Map.Entry<String, String> entry : params.entrySet()) {
                request.addHeader(entry.getKey(), entry.getValue());
            }

            ClassicHttpResponse response = client.execute(request);
            String responseBody = EntityUtils.toString(response.getEntity());

            Map<String, Object> result = new HashMap<>();
            result.put("status", response.getCode());
            Map<String, String> responseHeaders = new HashMap<>();
            Arrays.stream(response.getHeaders()).forEach(h -> responseHeaders.put(h.getName(), h.getValue()));
            result.put("headers", responseHeaders);
            result.put("payload", gson.fromJson(responseBody, Object.class));

            return createJsonResponse(ctx, result, 200);
        } catch (Exception e) {
            logger.error("External request failed for url={}", fullUrl, e);
            return createResponse(ctx, "Request failed: " + e.getMessage(), 500);
        }
    }

    private Object handleUsers(RequestContext ctx) {
        String user = ctx.queryParams.get("user");
        if (user != null) {
            setUserContext(user);
        }
        return createResponse(ctx, "Ok", 200);
    }

    // Utility methods

    private String retrieveArg(String key, String method, Map<String, String> queryParams, String body) {
        if ("GET".equals(method)) {
            return queryParams.get(key);
        } else if ("POST".equals(method) && body != null) {
            // Try URL-encoded form data
            try {
                Map<String, String> formData = parseFormData(body);
                if (formData.containsKey(key)) {
                    return formData.get(key);
                }
            } catch (Exception e) {
                logger.debug("Failed to parse body as form data for key '{}': {}", key, e.getMessage());
            }

            // Try JSON
            try {
                JsonObject json = JsonParser.parseString(body).getAsJsonObject();
                if (json.has(key)) {
                    return json.get(key).getAsString();
                }
            } catch (JsonSyntaxException e) {
                logger.debug("Failed to parse body as JSON for key '{}': {}", key, e.getMessage());
            } catch (Exception e) {
                logger.warn("Unexpected error parsing JSON for key '{}'", key, e);
            }

            // Try XML
            try {
                JSONObject xmlJson = XML.toJSONObject(body);
                if (xmlJson.has(key)) {
                    return xmlJson.getString(key);
                }
            } catch (Exception e) {
                logger.debug("Failed to parse body as XML for key '{}': {}", key, e.getMessage());
            }
        }
        return null;
    }

    private Map<String, String> parseFormData(String body) {
        Map<String, String> result = new HashMap<>();
        if (body == null || body.isEmpty()) {
            return result;
        }
        String[] pairs = body.split("&");
        for (String pair : pairs) {
            String[] keyValue = pair.split("=", 2);
            if (keyValue.length == 2) {
                try {
                    result.put(URLDecoder.decode(keyValue[0], "UTF-8"),
                            URLDecoder.decode(keyValue[1], "UTF-8"));
                } catch (UnsupportedEncodingException e) {
                    logger.debug("Failed to decode form pair: {}", pair);
                    result.put(keyValue[0], keyValue[1]);
                }
            }
        }
        return result;
    }

    private Map<String, String> parseQueryString(String queryString) {
        Map<String, String> result = new HashMap<>();
        if (queryString == null || queryString.isEmpty()) {
            return result;
        }
        return parseFormData(queryString);
    }

    private Map<String, Object> versionInfo() {
        String version;
        ClassLoader cl = ClassLoader.getSystemClassLoader();

        try {
            InputStream versionStream = cl.getResourceAsStream("dd-java-agent.version");
            if (versionStream == null) {
                logger.warn("dd-java-agent.version resource not found");
                version = "unknown";
            } else {
                try (BufferedReader reader =
                        new BufferedReader(
                                new InputStreamReader(versionStream, StandardCharsets.ISO_8859_1))) {
                    String line = reader.readLine();
                    version = (line != null && !line.isEmpty()) ? line : "unknown";
                }
            }
        } catch (IOException e) {
            logger.error("Failed to read dd-java-agent.version", e);
            version = "unknown";
        } catch (Exception e) {
            logger.error("Unexpected error reading version", e);
            version = "unknown";
        }

        Map<String, Object> info = new HashMap<>();
        info.put("status", "ok");
        Map<String, String> library = new HashMap<>();
        library.put("name", "java_lambda");
        library.put("version", version);
        info.put("library", library);
        return info;
    }

    // Response creation methods

    private Object createResponse(RequestContext ctx, String body, int statusCode) {
        return createResponse(ctx, body, statusCode, null);
    }

    private Object createResponse(RequestContext ctx, String body, int statusCode, Map<String, String> headers) {
        if (ctx.responseType == ResponseType.API_GATEWAY_HTTP) {
            APIGatewayV2HTTPResponse response = new APIGatewayV2HTTPResponse();
            response.setStatusCode(statusCode);
            response.setBody(body);
            response.setHeaders(headers != null ? headers : new HashMap<>());
            return response;
        } else {
            APIGatewayProxyResponseEvent response = new APIGatewayProxyResponseEvent();
            response.setStatusCode(statusCode);
            response.setBody(body);
            response.setHeaders(headers != null ? headers : new HashMap<>());
            return response;
        }
    }

    private Object createJsonResponse(RequestContext ctx, Object data, int statusCode) {
        String body = gson.toJson(data);
        Map<String, String> headers = new HashMap<>();
        headers.put("Content-Type", "application/json");
        return createResponse(ctx, body, statusCode, headers);
    }

    private Object createResponseWithCookies(RequestContext ctx, String body, int statusCode,
                                              Map<String, String> headers, Map<String, String> cookies) {
        if (headers == null) {
            headers = new HashMap<>();
        }

        if (cookies != null && !cookies.isEmpty()) {
            // For API Gateway, we need to handle Set-Cookie specially
            // Each cookie should be a separate Set-Cookie header
            if (ctx.responseType == ResponseType.API_GATEWAY_HTTP) {
                APIGatewayV2HTTPResponse response = new APIGatewayV2HTTPResponse();
                response.setStatusCode(statusCode);
                response.setBody(body);
                response.setHeaders(headers);

                // Set cookies as multi-value headers
                List<String> cookieHeaders = cookies.entrySet().stream()
                        .map(e -> e.getKey() + "=" + e.getValue() + "; Path=/; HttpOnly")
                        .collect(Collectors.toList());
                response.setCookies(cookieHeaders);
                return response;
            } else {
                APIGatewayProxyResponseEvent response = new APIGatewayProxyResponseEvent();
                response.setStatusCode(statusCode);
                response.setBody(body);

                // For REST API, use multiValueHeaders
                Map<String, List<String>> multiValueHeaders = new HashMap<>();
                List<String> setCookieValues = cookies.entrySet().stream()
                        .map(e -> e.getKey() + "=" + e.getValue() + "; Path=/; HttpOnly")
                        .collect(Collectors.toList());
                multiValueHeaders.put("Set-Cookie", setCookieValues);

                response.setHeaders(headers);
                response.setMultiValueHeaders(multiValueHeaders);
                return response;
            }
        }

        return createResponse(ctx, body, statusCode, headers);
    }

    private Object createErrorResponse(RequestContext ctx, String message, int statusCode) {
        Map<String, String> error = new HashMap<>();
        error.put("error", message);
        return createJsonResponse(ctx, error, statusCode);
    }

    // Datadog tracing methods

    private void trackCustomEvent(String value) {
        try {
            Map<String, String> metadata = new HashMap<>();
            metadata.put("value", value);
            EventTracker tracker = datadog.trace.api.GlobalTracer.getEventTracker();
            tracker.trackCustomEvent(TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata);
        } catch (Exception e) {
            logger.error("Failed to track custom event", e);
        }
    }

    private void trackUserLoginSuccessEvent() {
        try {
            Map<String, String> metadata = new HashMap<>();
            metadata.put("metadata0", "value0");
            metadata.put("metadata1", "value1");
            EventTracker tracker = datadog.trace.api.GlobalTracer.getEventTracker();
            tracker.trackLoginSuccessEvent(TRACK_USER, metadata);
        } catch (Exception e) {
            logger.error("Failed to track user login success event", e);
        }
    }

    private void setUserContext(String userId) {
        try {
            Map<String, String> metadata = new HashMap<>();
            metadata.put("email", "usr.email");
            metadata.put("name", "usr.name");
            metadata.put("session_id", "usr.session_id");
            metadata.put("role", "usr.role");
            metadata.put("scope", "usr.scope");
            setUser(userId, metadata);  // Now available with dd-trace-api 1.47.0+
        } catch (Exception e) {
            logger.error("Failed to set user", e);
        }
    }
}
