package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.security.AppSecAuthenticationFilter;
import com.datadoghq.system_tests.springboot.security.AppSecAuthenticationProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

@Configuration
public class WebSecurityConfig extends WebSecurityConfigurerAdapter{

    @Bean
    public AuthenticationManager authenticationManager() throws Exception {
        return new ProviderManager(new AppSecAuthenticationProvider());
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
}
