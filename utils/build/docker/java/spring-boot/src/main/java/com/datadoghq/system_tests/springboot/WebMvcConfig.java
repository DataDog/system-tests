package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.iast.XContentTypeInterceptor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import javax.annotation.Nonnull;

@Component
public class WebMvcConfig implements WebMvcConfigurer {

    private final XContentTypeInterceptor xContentTypeInterceptor;

    public WebMvcConfig(final XContentTypeInterceptor xContentTypeInterceptor) {
        this.xContentTypeInterceptor = xContentTypeInterceptor;
    }

    @Override
    public void addInterceptors(@Nonnull final InterceptorRegistry registry) {
        registry.addInterceptor(xContentTypeInterceptor);
    }
}
