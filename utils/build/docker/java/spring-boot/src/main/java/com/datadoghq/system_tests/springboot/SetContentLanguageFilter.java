package com.datadoghq.system_tests.springboot;

import java.io.IOException;
import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;

@Component
public class SetContentLanguageFilter implements Filter {
    // openliberty sets Content-Language: en-us to all the requests without such a
    // header. This interferes with the tst-037-009 rule, causing spurious blocking events
    @Override
    public void doFilter(ServletRequest servletRequest, ServletResponse servletResponse, FilterChain filterChain) throws IOException, ServletException {
        HttpServletResponse response = (HttpServletResponse) servletResponse;
        if (response.getHeader("content-language") == null) {
            response.setHeader("content-language", "pt-BR");
        }
        filterChain.doFilter(servletRequest, servletResponse);
    }
}
