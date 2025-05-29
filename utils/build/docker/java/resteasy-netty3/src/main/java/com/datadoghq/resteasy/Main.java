package com.datadoghq.resteasy;

import com.datadoghq.system_tests.iast.infra.LdapServer;
import com.datadoghq.system_tests.iast.infra.SqlServer;
import org.jboss.netty.bootstrap.ServerBootstrap;
import org.jboss.netty.channel.ChannelPipelineFactory;
import org.jboss.netty.channel.group.ChannelGroup;
import org.jboss.netty.channel.group.DefaultChannelGroup;
import org.jboss.netty.channel.socket.nio.NioServerSocketChannelFactory;
import org.jboss.resteasy.core.SynchronousDispatcher;
import org.jboss.resteasy.logging.Logger;
import org.jboss.resteasy.plugins.server.netty.HttpServerPipelineFactory;
import org.jboss.resteasy.plugins.server.netty.HttpsServerPipelineFactory;
import org.jboss.resteasy.plugins.server.netty.NettyJaxrsServer;
import org.jboss.resteasy.plugins.server.netty.RequestDispatcher;
import org.jboss.resteasy.spi.ResteasyDeployment;

import javax.naming.directory.InitialDirContext;
import javax.sql.DataSource;
import javax.ws.rs.core.Application;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.UndeclaredThrowableException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.Collections;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.logging.LogManager;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class Main {
    static {
        try {
            try (InputStream resourceAsStream = Main.class.getClassLoader().getResourceAsStream("logging.properties")) {
                LogManager.getLogManager().readConfiguration(
                        resourceAsStream);
            }
            org.jboss.resteasy.logging.Logger.setLoggerType(Logger.LoggerType.JUL);
        } catch (IOException e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    /**
     * Main method.
     * @param args
     */
    public static void main(String[] args) {
        var deployment = new ResteasyDeployment();
        deployment.setApplication(new Application() {
            private final Set<Object> singletons = Stream.of(
                    new MyResource(),
                    new IastSinkResource(),
                    new IastSourceResource(),
                    new RaspResource()
            ).collect(Collectors.toSet());

            @Override
            public Set<Object> getSingletons() {
                return singletons;
            }
        });

        // Register resources
//        deployment.getRegistry().addPerRequestResource(MyResource.class);
//        deployment.getRegistry().addPerRequestResource(RaspResource.class);
//        deployment.getRegistry().addPerRequestResource(IastSinkResource.class);
//        deployment.getRegistry().addPerRequestResource(IastSourceResource.class);
//        deployment.getRegistry().addPerRequestResource(IastSamplingResource.class);

        // we override start/stop to listen on 0.0.0.0
        var netty = new NettyJaxrsServer() {
            final ChannelGroup allChannels = new DefaultChannelGroup("NettyJaxrsServer");
            public void start() {
                this.deployment.start();
                RequestDispatcher dispatcher = new RequestDispatcher(
                        (SynchronousDispatcher)this.deployment.getDispatcher(),
                        this.deployment.getProviderFactory(), this.domain);
                this.bootstrap = new ServerBootstrap(new NioServerSocketChannelFactory(Executors.newCachedThreadPool(),
                        Executors.newCachedThreadPool(), Runtime.getRuntime().availableProcessors() * 2));
                var factory = new HttpServerPipelineFactory(
                        dispatcher, this.root, 16, 10485760);

                this.bootstrap.setPipelineFactory((ChannelPipelineFactory)factory);
                try {
                    this.channel = this.bootstrap.bind(
                            new InetSocketAddress(InetAddress.getByName("0.0.0.0"), this.port));
                } catch (UnknownHostException e) {
                    throw new UndeclaredThrowableException(e);
                }
                allChannels.add(this.channel);
            }

            public void stop() {
                allChannels.close().awaitUninterruptibly();
                if (this.bootstrap != null) {
                    this.bootstrap.releaseExternalResources();
                }

                this.deployment.stop();
            }
        };
        netty.setDeployment(deployment);
        netty.setPort(7777);
        netty.setRootResourcePath("");
        netty.setSecurityDomain(null);
        netty.start();

        while (!Thread.interrupted()) {
            try {
                Thread.sleep(60000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        netty.stop();
    }

    public static final DataSource DATA_SOURCE = new SqlServer().start();

    public static final InitialDirContext LDAP_CONTEXT = new LdapServer().start();
}

