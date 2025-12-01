package com.datadoghq.system_tests.springboot.security;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.provisioning.UserDetailsManager;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
public class AppSecSecurityController {

    private final UserDetailsManager userDetailsManager;

    public AppSecSecurityController(final UserDetailsManager userDetailsManager) {
        this.userDetailsManager = userDetailsManager;
    }

    @PostMapping("/signup")
    public ResponseEntity<String> signUp(@RequestParam String username, @RequestParam String password) {
        userDetailsManager.createUser(User.withUsername(username).password(password).roles("USER").build());
        return ResponseEntity.ok("Signup successful");
    }
}
