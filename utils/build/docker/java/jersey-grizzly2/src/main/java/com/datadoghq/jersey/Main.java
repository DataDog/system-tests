package com.datadoghq.jersey;

import com.datadoghq.system_tests.iast.infra.LdapServer;
import com.datadoghq.system_tests.iast.infra.SqlServer;
import org.glassfish.grizzly.http.server.HttpServer;
import org.glassfish.jersey.grizzly2.httpserver.GrizzlyHttpServerFactory;
import org.glassfish.jersey.server.ResourceConfig;

import javax.naming.directory.InitialDirContext;
import javax.sql.DataSource;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.UndeclaredThrowableException;
import java.net.URI;
import java.util.logging.LogManager;

/**
 * Main class.
 *
 */
public class Main {
    // Base URI the Grizzly HTTP server will listen on
    public static final String BASE_URI = "http://0.0.0.0:7777/";

    static {
        try {
            try (InputStream resourceAsStream = Main.class.getClassLoader().getResourceAsStream("logging.properties")) {
                LogManager.getLogManager().readConfiguration(
                        resourceAsStream);
            }
        } catch (IOException e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    /**
     * Starts Grizzly HTTP server exposing JAX-RS resources defined in this application.
     * @return Grizzly HTTP server.
     */
    public static HttpServer startServer() {
        // create a resource config that scans for JAX-RS resources and providers
        // in com.datadoghq.jersey package
        final ResourceConfig rc = new ResourceConfig().packages("com.datadoghq.jersey");

        // Register resources
        rc.register(MyResource.class);
        rc.register(RaspResource.class);
        rc.register(IastSinkResource.class);
        rc.register(IastSourceResource.class);
        rc.register(IastSamplingResource.class);

        // create and start a new instance of grizzly http server
        // exposing the Jersey application at BASE_URI
        return GrizzlyHttpServerFactory.createHttpServer(URI.create(BASE_URI), rc);
    }

    /**
     * Main method.
     * @param args
     * @throws IOException
     */
    public static void main(String[] args) throws IOException {
        final HttpServer server = startServer();
        System.out.println(String.format("Jersey app started with endpoints available at "
                + "%s", BASE_URI));
        while (!Thread.interrupted()) {
            try {
                Thread.sleep(60000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        server.shutdownNow();
    }

    public static final DataSource DATA_SOURCE = new SqlServer().start();

    public static final InitialDirContext LDAP_CONTEXT = new LdapServer().start();
}

