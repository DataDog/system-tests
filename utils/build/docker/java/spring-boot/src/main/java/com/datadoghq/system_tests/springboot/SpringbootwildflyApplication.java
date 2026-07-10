package com.datadoghq.system_tests.springboot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.support.SpringBootServletInitializer;

// Spring Boot 1.x
//import org.springframework.boot.web.support.SpringBootServletInitializer;

@SpringBootApplication
public class SpringbootwildflyApplication extends SpringBootServletInitializer {

    public static void main(String[] args) {
        // Child mode for the telemetry session-id tests: /spawn_child (fork=false) re-execs
        // this jar with DD_SYSTEM_TEST_CHILD_SLEEP set. The dd-java-agent has already started
        // the tracer (emitting telemetry with the session-id headers), so the child only needs
        // to stay alive briefly and exit. It must NOT boot the full app, which would clash on
        // the already-bound ports 7777/7778. This is the real entrypoint (App.main is unused).
        String childSleep = System.getenv("DD_SYSTEM_TEST_CHILD_SLEEP");
        if (childSleep != null) {
            try {
                Thread.sleep(Integer.parseInt(childSleep) * 1000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            if ("true".equals(System.getenv("DD_SYSTEM_TEST_CHILD_CRASH"))) {
                Runtime.getRuntime().halt(139);
            }
            return;
        }
        SpringApplication.run(applicationClass, args);
    }

    @Override
    protected SpringApplicationBuilder configure(SpringApplicationBuilder application) {
        return application.sources(applicationClass);
    }

    //private static Class<SpringbootwildflyApplication> applicationClass = SpringbootwildflyApplication.class;
    private static Class<App> applicationClass = App.class;
}


