package com.datadoghq.system_tests.iast.infra;

import org.hsqldb.jdbc.JDBCPool;

import javax.sql.DataSource;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.UndeclaredThrowableException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class SqlServer implements Server<DataSource> {

    private org.hsqldb.Server server;

    @Override
    public DataSource start() {
        if (server != null) {
            throw new IllegalStateException("Server already started");
        }
        try {
            server = new org.hsqldb.Server();
            server.setDatabasePath(0, "mem:vertxDb");
            server.start();
            Runtime.getRuntime().addShutdownHook(new Thread(this::close));
            final JDBCPool dataSource = new JDBCPool();
            dataSource.setURL("jdbc:hsqldb:mem:vertxDb");
            dataSource.setUser("SA");
            try (final Connection con = dataSource.getConnection()) {
                final String data = Stream.concat(getResource("schema.sql").lines(), getResource("data.sql").lines())
                        .collect(Collectors.joining("\n"));
                final List<String> statements = Arrays.stream(data.split(";"))
                        .map(String::trim)
                        .filter(it -> !it.isEmpty())
                        .collect(Collectors.toList());
                for (final String sql : statements) {
                    final PreparedStatement statement = con.prepareStatement(sql);
                    statement.execute();
                }
            }
            return dataSource;
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    @Override
    public void close() {
        if (server != null) {
            try {
                server.stop();
            } finally {
                server = null;
            }
        }
    }

    private static BufferedReader getResource(final String name) {
        final InputStream is = Thread.currentThread().getContextClassLoader().getResourceAsStream(name);
        if (is == null) {
            throw new RuntimeException("Failed to resolve resource : " + name);
        }
        return new BufferedReader(new InputStreamReader(is));
    }
}
