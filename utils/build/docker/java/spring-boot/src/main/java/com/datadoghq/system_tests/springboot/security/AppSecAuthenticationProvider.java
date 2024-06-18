package com.datadoghq.system_tests.springboot.security;

import datadog.trace.api.EventTracker;
import datadog.trace.api.GlobalTracer;
import org.springframework.security.authentication.AuthenticationProvider;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public class AppSecAuthenticationProvider implements AuthenticationProvider {

    private static final Map<String, AppSecUser> USERS = new HashMap<>();

    static {
        Arrays.asList(
                new AppSecUser("social-security-id", "test", "1234", "testuser@ddog.com"),
                new AppSecUser("591dc126-8431-4d0f-9509-b23318d3dce4", "testuuid", "1234", "testuseruuid@ddog.com")
        ).forEach(user -> USERS.put(user.getUsername(), user));
    }

    @Override
    public Authentication authenticate(Authentication authentication) throws AuthenticationException {
        AppSecSdkToken token = (AppSecSdkToken) authentication;
        if (token.getSdkEvent() == null) {
            return loginUserPassword(token);
        } else {
            return loginSdk(token);
        }
    }

    private Authentication loginUserPassword(final AppSecSdkToken auth) {
        String username = auth.getName();
        if (!USERS.containsKey(username)) {
            throw new UsernameNotFoundException(username);
        }
        final AppSecUser user = USERS.get(username);
        if (!user.getPassword().equals(auth.getCredentials())) {
            throw new BadCredentialsException(username);
        }
        return new AppSecSdkToken(new AppSecUser(user), auth.getCredentials(), Collections.emptyList());
    }

    private Authentication loginSdk(final AppSecSdkToken auth) {
        String username = auth.getSdkUser();
        Map<String, String> metadata = new HashMap<>();
        EventTracker tracker = GlobalTracer.getEventTracker();
        switch (auth.getSdkEvent()) {
            case "success":
                tracker.trackLoginSuccessEvent(username, metadata);
                return new AppSecSdkToken(username, auth.getCredentials(), Collections.emptyList());
            case "failure":
                tracker.trackLoginFailureEvent(username, auth.isSdkUserExists(), metadata);
                if (auth.isSdkUserExists()) {
                    throw new BadCredentialsException(username);
                } else {
                    throw new UsernameNotFoundException(username);
                }
            default:
                throw new IllegalArgumentException("Invalid SDK event: " + auth.getSdkEvent());
        }

    }

    @Override
    public boolean supports(Class<?> authentication) {
        return AppSecSdkToken.class.isAssignableFrom(authentication);
    }


}
