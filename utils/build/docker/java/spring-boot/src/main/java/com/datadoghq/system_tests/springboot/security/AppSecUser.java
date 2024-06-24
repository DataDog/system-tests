package com.datadoghq.system_tests.springboot.security;

import org.springframework.security.core.userdetails.User;

import java.util.Collections;

public class AppSecUser extends User {

    private final String id;
    private final String email;

    public AppSecUser(String id, String username, String password, String email) {
        super(username, password, Collections.emptyList());
        this.id = id;
        this.email = email;
    }

    public AppSecUser(AppSecUser user) {
        this(user.getId(), user.getUsername(), user.getPassword(), user.getEmail());
    }

    public String getEmail() {
        return email;
    }

    public String getId() {
        return id;
    }
}