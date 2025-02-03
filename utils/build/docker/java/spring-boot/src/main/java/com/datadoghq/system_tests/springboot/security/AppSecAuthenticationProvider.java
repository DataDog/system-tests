package com.datadoghq.system_tests.springboot.security;

import datadog.trace.api.EventTracker;
import datadog.trace.api.GlobalTracer;
import org.springframework.security.authentication.AuthenticationProvider;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.provisioning.UserDetailsManager;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public class AppSecAuthenticationProvider implements AuthenticationProvider {

    private final UserDetailsManager userDetailsManager;

    public AppSecAuthenticationProvider(final UserDetailsManager userDetailsManager) {
        this.userDetailsManager = userDetailsManager;
    }

    @Override
    public Authentication authenticate(Authentication authentication) throws AuthenticationException {
        AppSecToken token = (AppSecToken) authentication;
        return loginUserPassword(token);
    }

    private Authentication loginUserPassword(final AppSecToken auth) {
        String username = auth.getName();
        if (!userDetailsManager.userExists(username)) {
            throw new UsernameNotFoundException(username);
        }
        final AppSecUser user = (AppSecUser) userDetailsManager.loadUserByUsername(username);
        if (!user.getPassword().equals(auth.getCredentials())) {
            throw new BadCredentialsException(username);
        }
        return new AppSecToken(new AppSecUser(user), auth.getCredentials(), Collections.emptyList());
    }

    @Override
    public boolean supports(Class<?> authentication) {
        return AppSecToken.class.isAssignableFrom(authentication);
    }


}
