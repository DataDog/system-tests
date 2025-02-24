package com.datadoghq.system_tests.springboot.security;

import datadog.trace.api.EventTracker;
import datadog.trace.api.GlobalTracer;
import org.checkerframework.checker.units.qual.A;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.web.authentication.AbstractAuthenticationProcessingFilter;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.util.Base64Utils;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class AppSecAuthenticationFilter extends AbstractAuthenticationProcessingFilter {

    private enum SdkTrigger {
        BEFORE,
        AFTER,
        NONE;

        public static SdkTrigger get(final HttpServletRequest request) {
            if (request.getParameter("sdk_event") == null) {
                return NONE;
            }
            final String trigger = request.getParameter("sdk_trigger");
            if (trigger == null || "after".equalsIgnoreCase(trigger)) {
                return AFTER;
            }
            return BEFORE;
        }
    }

    public AppSecAuthenticationFilter(String url, AuthenticationManager authenticationManager) {
        super(new AntPathRequestMatcher(url), authenticationManager);
        this.setAuthenticationSuccessHandler((request, response, authentication) -> {
            response.setStatus(HttpStatus.OK.value());
        });
        this.setAuthenticationFailureHandler((request, response, exception) -> {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
        });
    }

    @Override
    public Authentication attemptAuthentication(HttpServletRequest request, HttpServletResponse response) throws AuthenticationException, IOException, ServletException {
        final String auth = request.getParameter("auth");
        String username, password;
        switch (auth) {
            case "local":
                username = request.getParameter("username");
                password = request.getParameter("password");
                break;
            case "basic":
                String header = request.getHeader("Authorization");
                String[] parts = header.split("\\s+");
                assert parts.length == 2;
                assert parts[0].equals("Basic");
                String[] usernamePassword = new String(Base64Utils.decodeFromString(parts[1])).split(":");
                username = usernamePassword[0];
                password = usernamePassword[1];
                break;
            default:
                return null;
        }
        final SdkTrigger trigger = SdkTrigger.get(request);
        AuthenticationException sdkException = trigger == SdkTrigger.BEFORE ? triggerSdk(request) : null;
        try {
            return this.getAuthenticationManager().authenticate(new AppSecToken(username, password));
        } finally {
            sdkException = trigger == SdkTrigger.AFTER ? triggerSdk(request) : sdkException;
            if (sdkException != null) {
                throw sdkException;
            }
        }
    }

    private AuthenticationException triggerSdk(final HttpServletRequest request) {
        final String sdkEvent = request.getParameter("sdk_event");
        final String sdkUser = request.getParameter("sdk_user");
        final boolean sdkUserExists = Boolean.parseBoolean(request.getParameter("sdk_user_exists"));
        final EventTracker tracker = GlobalTracer.getEventTracker();
        final Map<String, String> metadata = new HashMap<>();
        switch (sdkEvent) {
            case "success":
                tracker.trackLoginSuccessEvent(sdkUser, metadata);
                return null;
            case "failure":
                tracker.trackLoginFailureEvent(sdkUser, sdkUserExists, metadata);
                return new BadCredentialsException(sdkUser);
            default:
                throw new IllegalArgumentException("Invalid SDK event: " + sdkEvent);
        }
    }
}
