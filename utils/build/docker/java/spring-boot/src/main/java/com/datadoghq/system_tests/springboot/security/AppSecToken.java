package com.datadoghq.system_tests.springboot.security;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;

import java.util.Collection;

public class AppSecToken extends UsernamePasswordAuthenticationToken {

    public AppSecToken(Object principal, Object credentials) {
        super(principal, credentials);
    }

    public AppSecToken(Object principal, Object credentials,
                       Collection<? extends GrantedAuthority> authorities) {
        super(principal, credentials, authorities);
    }
}
