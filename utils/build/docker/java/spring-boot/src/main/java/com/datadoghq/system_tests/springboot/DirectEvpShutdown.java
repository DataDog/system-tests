package com.datadoghq.system_tests.springboot;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicBoolean;
import org.springframework.context.ConfigurableApplicationContext;
import sun.misc.Signal;

/** Opt-in SIGTERM lifecycle used only by the direct-EVP shutdown system test. */
final class DirectEvpShutdown {
    private static final String ENABLE_ENV = "SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED";

    private DirectEvpShutdown() {}

    static void install(ConfigurableApplicationContext context) {
        if (!"true".equals(System.getenv(ENABLE_ENV))) {
            return;
        }

        AtomicBoolean stopping = new AtomicBoolean();
        Signal.handle(new Signal("TERM"), signal -> {
            if (!stopping.compareAndSet(false, true)) {
                return;
            }

            int exitCode = 0;
            try {
                context.close();
                System.out.println(
                    "{\"event\":\"system_tests.ffe.shutdown.server_closed\",\"timestamp\":\""
                        + Instant.now()
                        + "\"}"
                );
            } catch (Throwable error) {
                error.printStackTrace(System.err);
                exitCode = 1;
            }
            System.exit(exitCode);
        });
    }
}
