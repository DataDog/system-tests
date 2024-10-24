package com.datadoghq.system_tests.springboot.security;

import static java.util.Collections.emptyList;

import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.authentication.AbstractAuthenticationProcessingFilter;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.util.Base64Utils;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

public class AppSecAuthenticationFilter extends AbstractAuthenticationProcessingFilter {

    public AppSecAuthenticationFilter(String url, AuthenticationManager authenticationManager) {
        super(new AntPathRequestMatcher(url), authenticationManager);
        this.setAuthenticationSuccessHandler((request, response, authentication) -> {
            response.getWriter().write("Hello " + authentication.getName());
            response.setStatus(HttpStatus.OK.value());
        });
        this.setAuthenticationFailureHandler((request, response, exception) -> {
            response.sendError(HttpStatus.UNAUTHORIZED.value(), exception.getMessage());
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
        Authentication authentication;
        String sdkEvent = request.getParameter("sdk_event");
        if (sdkEvent != null) {
            String sdkUser = request.getParameter("sdk_user");
            boolean sdkUserExists = Boolean.parseBoolean(request.getParameter("sdk_user_exists"));
            authentication = new AppSecSdkToken(username, password, sdkEvent, sdkUser, sdkUserExists);
        } else {
            authentication = new AppSecSdkToken(username, password);
        }
        return this.getAuthenticationManager().authenticate(authentication);
    }
}
