package com.datadoghq;

import static java.util.concurrent.TimeUnit.SECONDS;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

public class App {
    private static final String SERVER_PORT_ARG = "APM_TEST_CLIENT_SERVER_PORT";
    static final Logger LOGGER = LoggerFactory.getLogger(App.class.getName());

    public App() throws ReflectiveOperationException, IOException {
        int port = getServerPort();
        startServer(port);
    }

    public static void main(String[] args) {
        try {
            new App();
        } catch (ReflectiveOperationException e) {
            LOGGER.error("Failed to get internal logger API.", e);
        } catch (IOException e) {
            LOGGER.error("Failed to start gRPC server.", e);
        }
    }

    private int getServerPort() {
        String portString = System.getenv(SERVER_PORT_ARG);
        if (portString == null) {
            LOGGER.error("Missing {} environment variable.", SERVER_PORT_ARG);
            System.exit(1);
        }
        try {
            return Integer.parseInt(portString);
        } catch (NumberFormatException e) {
            LOGGER.error("Invalid {} environment variable value: {}.", SERVER_PORT_ARG, portString);
            System.exit(1);
            return -1;
        }
    }

    private void startServer(int port) throws IOException {
        Server server = ServerBuilder.forPort(port)
                .addService(new ApmClientImpl())
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
            LOGGER.warn("Failed to wait for server termination.", e);
        }
    }
}
