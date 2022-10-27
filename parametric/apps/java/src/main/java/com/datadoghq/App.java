package com.datadoghq;

import static java.util.concurrent.TimeUnit.SECONDS;
import static java.util.logging.Level.SEVERE;
import static java.util.logging.Level.WARNING;

import datadog.opentracing.DDTracer;
import datadog.trace.common.metrics.MetricsAggregator;
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
    private Runnable flushTraceRunnable;
    private Runnable flushStatsRunnable;

    public App() throws ReflectiveOperationException, IOException {
        this.tracer = createTracer();
        extractFlushRunnable();
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
                .addService(new ApmClientImpl(
                        this.tracer,
                        this.flushTraceRunnable,
                        this.flushStatsRunnable
                ))
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

    private void extractFlushRunnable() throws ReflectiveOperationException {
        for (Field field : DDTracer.class.getDeclaredFields()) {
            if ("tracer".equals(field.getName())) {
                field.setAccessible(true);
                CoreTracer tracerApi = (CoreTracer) field.get(this.tracer);
//              this.flushTraceRunnable = tracerApi::flush;
                // TODO How to ensure trace flush? Is closing a solution in Java library?
                this.flushTraceRunnable = () -> {
                        tracerApi.flush();
//                        tracer.close();
                };
                extractFlushStatsRunnable(tracerApi);
                return;
            }
        }
        throw new NoSuchFieldException("tracer");
    }

    private void extractFlushStatsRunnable(CoreTracer tracerApi) throws ReflectiveOperationException {
        for (Field field : CoreTracer.class.getDeclaredFields()) {
           if ("metricsAggregator".equals(field.getName())) {
               field.setAccessible(true);
                MetricsAggregator aggregator = (MetricsAggregator) field.get(tracerApi);
//              this.flushStatsRunnable = aggregator::report;
                // TODO How to ensure to flush metrics? Wait long enough to be sure to flush (every 10s by default)
                this.flushStatsRunnable = () -> {
                    aggregator.report();
//                  tracer.close();
                    try {
                        Thread.sleep(15_000);
                    } catch (InterruptedException e) {
                        throw new RuntimeException(e);
                    }
                };
                return;
            }
        }
        throw new NoSuchFieldException("metricsAggregator");
    }
}
