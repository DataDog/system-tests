package com.datadoghq.system_tests.springboot;


import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.session.web.http.CookieSerializer;
import org.springframework.session.web.http.DefaultCookieSerializer;

@Configuration
public class CookieConfig {

    @Bean
    CookieSerializer cookieSerializer() {
        DefaultCookieSerializer defaultCookieSerializer = new DefaultCookieSerializer();
        defaultCookieSerializer.setCookieName("CUSTOMSESSIONID");
        defaultCookieSerializer.setUseHttpOnlyCookie(true);
        defaultCookieSerializer.setUseSecureCookie(true);
        defaultCookieSerializer.setSameSite("Strict");
        return defaultCookieSerializer;

    }
}
