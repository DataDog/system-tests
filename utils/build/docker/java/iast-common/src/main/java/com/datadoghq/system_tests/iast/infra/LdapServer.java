package com.datadoghq.system_tests.iast.infra;

import com.unboundid.ldap.listener.InMemoryDirectoryServer;
import com.unboundid.ldap.listener.InMemoryDirectoryServerConfig;
import com.unboundid.ldif.LDIFReader;

import javax.naming.Context;
import javax.naming.directory.InitialDirContext;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.UndeclaredThrowableException;
import java.util.Hashtable;

public class LdapServer implements Server<InitialDirContext>  {

    private InMemoryDirectoryServer server;

    @Override
    public InitialDirContext start() {
        if (server != null) {
            throw new IllegalStateException("Server already started");
        }
        try {
            final InMemoryDirectoryServerConfig config = new InMemoryDirectoryServerConfig("dc=example");
            server = new InMemoryDirectoryServer(config);
            server.importFromLDIF(true, new LDIFReader(getResource("test-server.ldif")));
            server.startListening();
            Runtime.getRuntime().addShutdownHook(new Thread(this::close));
            final String url = String.format("ldap://localhost:%s/dc=example", server.getListenPort());
            Hashtable<String, String> env = new Hashtable<>(3);
            env.put(Context.INITIAL_CONTEXT_FACTORY, "com.sun.jndi.ldap.LdapCtxFactory");
            env.put(Context.PROVIDER_URL, url);
            env.put(Context.SECURITY_AUTHENTICATION, "none");
            return new InitialDirContext(env);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    @Override
    public void close() {
        if (server != null) {
            try {
                server.close();
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
