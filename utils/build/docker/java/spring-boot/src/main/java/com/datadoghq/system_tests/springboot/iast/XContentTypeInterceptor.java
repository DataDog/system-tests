package com.datadoghq.system_tests.springboot.iast;

import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.ModelAndView;

import javax.annotation.Nonnull;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@Component
public class XContentTypeInterceptor implements HandlerInterceptor {

    private static final String XCONTENT_ENDPOINT = "/iast/xcontent-missing-header";
    private static final String  XCONTENT_TYPE_HEADER = "X-Content-Type-Options";
    private static final String NOSNIFF = "nosniff";

    @Override
    public void postHandle(@Nonnull final HttpServletRequest request,
                           @Nonnull final HttpServletResponse response,
                           @Nonnull final Object handler,
                           final ModelAndView modelAndView) throws Exception {
        if (!isXContentTypeVulnerabilityEndpoint(request)) {
            // XXX: Avoid triggering XCONTENTTYPE_MISSING_HEADER vulnerability.
            response.setHeader(XCONTENT_TYPE_HEADER, NOSNIFF);
        }
    }

    private boolean isXContentTypeVulnerabilityEndpoint(final HttpServletRequest request) {
        final String requestUri = request.getRequestURI();
        return requestUri != null && requestUri.contains(XCONTENT_ENDPOINT);
    }
}
