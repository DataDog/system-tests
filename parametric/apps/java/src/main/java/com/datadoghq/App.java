package com.datadoghq;

import static java.util.concurrent.TimeUnit.SECONDS;
import static java.util.logging.Level.SEVERE;
import static java.util.logging.Level.WARNING;

import datadog.opentracing.DDTracer;
import datadog.trace.core.CoreTracer;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.opentracing.util.GlobalTracer;

import java.io.IOException;
import java.lang.reflect.Field;
import java.util.logging.Logger;

public class App {
    static final Logger LOGGER = Logger.getLogger(App.class.getName());
    private static final int CLIENT_SERVER_PORT = 50051;
    private final DDTracer tracer;
    private final Runnable flushTracerRunnable;

    public App() throws ReflectiveOperationException, IOException {
        this.tracer = createTracer();
        this.flushTracerRunnable = createFlushRunnable();
        startServer(CLIENT_SERVER_PORT);
    }

    public static void main(String[] args) {
        try {
            new App();
        } catch (ReflectiveOperationException e) {
            LOGGER.log(SEVERE, "Failed to get internal logger API.", e);
        } catch (IOException e) {
            LOGGER.log(SEVERE, "Failed to start gRPC server.", e);
        }
    }

    private void startServer(int port) throws IOException {
        Server server = ServerBuilder.forPort(port)
                .addService(new ApmClientImpl(GlobalTracer.get(), this.flushTracerRunnable))
                .build()
                .start();
        LOGGER.info("Server started at port " + port + ".");
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            // Start graceful shutdown
            server.shutdown();
            try {
                // Wait for RPCs to complete processing
                if (!server.awaitTermination(30, SECONDS)) {
                    // That was plenty of time. Let's cancel the remaining RPCs
                    server.shutdownNow();
                    // shutdownNow isn't instantaneous, so give a bit of time to clean resources up
                    // gracefully. Normally this will be well under a second.
                    server.awaitTermination(5, SECONDS);
                }
            } catch (InterruptedException ex) {
                server.shutdownNow();
            }
        }));
        try {
            server.awaitTermination();
        } catch (InterruptedException e) {
            LOGGER.log(WARNING, "Failed to wait for server termination.", e);
        }
    }

    private DDTracer createTracer() {
        DDTracer tracer = new DDTracer.DDTracerBuilder().build();
        GlobalTracer.registerIfAbsent(tracer);
        return tracer;
    }

    private Runnable createFlushRunnable() throws ReflectiveOperationException {
        for (Field declaredField : DDTracer.class.getDeclaredFields()) {
            if ("tracer".equals(declaredField.getName())) {
                declaredField.setAccessible(true);
                CoreTracer tracerApi = (CoreTracer) declaredField.get(this.tracer);
                return tracerApi::flush;
            }
        }
        throw new NoSuchFieldException("tracer");
    }
}
