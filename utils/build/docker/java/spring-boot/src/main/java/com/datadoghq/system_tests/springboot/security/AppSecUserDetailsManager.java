package com.datadoghq.system_tests.springboot.security;

import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.provisioning.UserDetailsManager;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

public class AppSecUserDetailsManager implements UserDetailsManager {

    private static final Map<String, AppSecUser> USERS = new HashMap<>();

    static {
        Arrays.asList(
                new AppSecUser("social-security-id", "test", "1234", "testuser@ddog.com"),
                new AppSecUser("591dc126-8431-4d0f-9509-b23318d3dce4", "testuuid", "1234", "testuseruuid@ddog.com")
        ).forEach(user -> USERS.put(user.getUsername(), user));
    }

    @Override
    public UserDetails loadUserByUsername(final String username) throws UsernameNotFoundException {
        return USERS.get(username);
    }

    @Override
    public void createUser(final UserDetails user) {
        // ignore it
    }

    @Override
    public void updateUser(UserDetails user) {
        throw new UnsupportedOperationException();
    }

    @Override
    public void deleteUser(String username) {
        throw new UnsupportedOperationException();
    }

    @Override
    public void changePassword(String oldPassword, String newPassword) {
        throw new UnsupportedOperationException();
    }

    @Override
    public boolean userExists(String username) {
        return USERS.containsKey(username);
    }


}
