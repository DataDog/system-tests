package com.datadoghq.system_tests.springboot.security;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;

import java.util.Collection;

/**
 * Token used to bypass appsec auto user instrumentation when using the SDK
 */
public class AppSecSdkToken extends UsernamePasswordAuthenticationToken {

    private String sdkEvent;

    private String sdkUser;

    private boolean sdkUserExists;

    public AppSecSdkToken(Object principal, Object credentials) {
        this(principal, credentials, null, null, false);
    }

    public AppSecSdkToken(Object principal, Object credentials, String sdkEvent, String sdkUser, boolean sdkUserExists) {
        super(principal, credentials);
        this.sdkEvent = sdkEvent;
        this.sdkUser = sdkUser;
        this.sdkUserExists = sdkUserExists;
    }

    public AppSecSdkToken(Object principal, Object credentials,
                          Collection<? extends GrantedAuthority> authorities) {
        super(principal, credentials, authorities);
    }

    @Override
    public String getName() {
        if (getPrincipal() instanceof AppSecUser) {
            // report the id instead of the username
            return ((AppSecUser) getPrincipal()).getId();
        }
        return super.getName();
    }

    public String getSdkEvent() {
        return sdkEvent;
    }

    public String getSdkUser() {
        return sdkUser;
    }

    public boolean isSdkUserExists() {
        return sdkUserExists;
    }
}
