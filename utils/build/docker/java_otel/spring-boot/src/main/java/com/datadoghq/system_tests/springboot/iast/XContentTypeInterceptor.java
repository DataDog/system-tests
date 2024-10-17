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
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!isXContentTypeVulnerabilityEndpoint(request)) {
            response.setHeader(XCONTENT_TYPE_HEADER, NOSNIFF);
        }
        return true;
    }

    private boolean isXContentTypeVulnerabilityEndpoint(final HttpServletRequest request) {
        final String requestUri = request.getRequestURI();
        return requestUri != null && requestUri.contains(XCONTENT_ENDPOINT);
    }
}
