package com.datadoghq.ratpack;

import ratpack.handling.Chain;
import ratpack.handling.Handler;

/**
 * Routes for the RFC-1125 normalized route tests (tests/appsec/api_security_testing/test_normalized_route.py).
 * Ratpack path tokens take a whole segment, so routes with several parameters or static text in one
 * segment cannot be declared.
 */
final class NormalizedRouteHandlers {

    private NormalizedRouteHandlers() {}

    static void register(final Chain chain) throws Exception {
        final Handler ok = ctx -> ctx.getResponse().send("text/plain", "ok");
        chain.get("api_security/optional-segment/:id/:tab?", ok)
                .get("api_security/optional-chain/:x?/:y?", ok)
                .prefix("api_security/catch-all", catchAll -> catchAll.all(ok))
                .get("api_security/encoded/caf%C3%A9", ok) // Ratpack matches the encoded path
                .get("api_security/drafts", ok)
                .get("api_security/drafts/preview", ok);
    }
}
