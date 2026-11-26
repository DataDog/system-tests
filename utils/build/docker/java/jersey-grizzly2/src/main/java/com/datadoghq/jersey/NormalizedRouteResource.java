package com.datadoghq.jersey;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

/**
 * Routes for the RFC-1125 normalized route tests (tests/appsec/api_security_testing/test_normalized_route.py).
 * Only the declared templates matter: the handlers do not read the path parameters.
 */
@Path("/api_security")
@Produces(MediaType.TEXT_PLAIN)
public class NormalizedRouteResource {

    private static final String OK = "ok";

    @GET
    @Path("/multi-params-in-segment/{id}.{format}")
    public String multiParamsInSegment() {
        return OK;
    }

    @GET
    @Path("/three-params/{a}-{b}-{c}")
    public String threeParams() {
        return OK;
    }

    @GET
    @Path("/optional-params/{id}")
    public String optionalParams() {
        return OK;
    }

    @GET
    @Path("/optional-params/{id}.{format}")
    public String optionalParamsWithFormat() {
        return OK;
    }

    @GET
    @Path("/static-text/user-{id}")
    public String staticText() {
        return OK;
    }

    @GET
    @Path("/version/v{version}/items")
    public String staticTextBeforeParam() {
        return OK;
    }

    @GET
    @Path("/files/{name}.json")
    public String staticTextAfterParam() {
        return OK;
    }

    @GET
    @Path("/optional-segment/{id}")
    public String optionalSegment() {
        return OK;
    }

    @GET
    @Path("/optional-segment/{id}/{tab}")
    public String optionalSegmentWithTab() {
        return OK;
    }

    @GET
    @Path("/search")
    public String search() {
        return OK;
    }

    @GET
    @Path("/search.{format}")
    public String searchWithFormat() {
        return OK;
    }

    @GET
    @Path("/optional-chain")
    public String optionalChain() {
        return OK;
    }

    @GET
    @Path("/optional-chain/{x}")
    public String optionalChainX() {
        return OK;
    }

    @GET
    @Path("/optional-chain/{x}/{y}")
    public String optionalChainXY() {
        return OK;
    }

    @GET
    @Path("/catch-all/{path: .*}")
    public String catchAll() {
        return OK;
    }

    @GET
    @Path("/encoded/caf\u00e9")
    public String encoded() {
        return OK;
    }

    @GET
    @Path("/param-names/{user-id}/{user_id}")
    public String paramNames() {
        return OK;
    }

    @GET
    @Path("/drafts")
    public String drafts() {
        return OK;
    }

    @GET
    @Path("/drafts/preview")
    public String draftsPreview() {
        return OK;
    }
}
