package com.datadoghq.vertx4;

import io.vertx.ext.web.Router;
import java.util.function.Consumer;

/**
 * Routes for the RFC-1125 normalized route tests (tests/appsec/api_security_testing/test_normalized_route.py).
 * Only the declared paths matter. Vert.x parameter names are limited to letters, digits and '_', so
 * /api_security/param-names/{user-id}/{user_id} cannot be declared.
 */
public class NormalizedRouteProvider implements Consumer<Router> {

    private static final String[] PATHS = {
        "/api_security/multi-params-in-segment/:id.:format",
        "/api_security/three-params/:a-:b-:c",
        "/api_security/optional-params/:id.:format",
        "/api_security/optional-params/:id",
        "/api_security/static-text/user-:id",
        "/api_security/version/v:version/items",
        "/api_security/files/:name.json",
        "/api_security/optional-segment/:id",
        "/api_security/optional-segment/:id/:tab",
        "/api_security/search",
        "/api_security/search.:format",
        "/api_security/optional-chain",
        "/api_security/optional-chain/:x",
        "/api_security/optional-chain/:x/:y",
        "/api_security/catch-all/*",
        "/api_security/encoded/caf%C3%A9", // Vert.x matches the encoded path
        "/api_security/drafts",
        "/api_security/drafts/preview",
    };

    @Override
    public void accept(final Router router) {
        for (final String path : PATHS) {
            router.get(path).handler(ctx -> ctx.response().end("ok"));
        }
    }
}
