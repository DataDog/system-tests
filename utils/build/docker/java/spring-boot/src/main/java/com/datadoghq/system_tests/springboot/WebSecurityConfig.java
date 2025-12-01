package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.security.AppSecAuthenticationFilter;
import com.datadoghq.system_tests.springboot.security.AppSecAuthenticationProvider;
import com.datadoghq.system_tests.springboot.security.AppSecUserDetailsManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.provisioning.UserDetailsManager;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.firewall.StrictHttpFirewall;

import java.util.Arrays;

@Configuration
public class WebSecurityConfig extends WebSecurityConfigurerAdapter{

    @Bean
    public AuthenticationManager authenticationManager() throws Exception {
        return new ProviderManager(new AppSecAuthenticationProvider(userDetailsManager()));
    }

    @Bean
    public UserDetailsManager userDetailsManager() {
        return new AppSecUserDetailsManager();
    }

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        AuthenticationManager manager = authenticationManager();
        http
            .authenticationManager(manager)
            .addFilterBefore(new AppSecAuthenticationFilter("/login", manager), UsernamePasswordAuthenticationFilter.class)
            .authorizeRequests()
                    .antMatchers("/login").authenticated()
                    .anyRequest().permitAll()
            .and()
            .csrf().disable()
            .headers().disable();
    }

    @Bean
    public StrictHttpFirewall allowTraceHttpFirewall() {
        StrictHttpFirewall firewall = new StrictHttpFirewall();
        firewall.setAllowedHttpMethods(Arrays.asList("TRACE", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"));
        return firewall;
    }
}
