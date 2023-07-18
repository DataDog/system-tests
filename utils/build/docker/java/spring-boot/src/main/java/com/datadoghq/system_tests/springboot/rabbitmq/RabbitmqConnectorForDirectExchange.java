package com.datadoghq.system_tests.springboot.rabbitmq;

import com.rabbitmq.client.BuiltinExchangeType;
import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.client.Consumer;
import com.rabbitmq.client.DefaultConsumer;
import com.rabbitmq.client.Envelope;
import com.rabbitmq.client.AMQP.BasicProperties;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.io.StringWriter;
import java.io.PrintWriter;
import java.net.InetSocketAddress;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.ThreadLocalRandom;

public class RabbitmqConnectorForDirectExchange extends RabbitmqConnector {
	private static final String DIRECT_EXCHANGE_NAME = "systemTestDirectExchange";
	private static final String DIRECT_ROUTING_KEY = "systemTestDirectRoutingKey";
	private static final String QUEUE = "systemTestRabbitmqQueue";

	private void init(Channel channel) throws Exception {
	    // exchange and queue declarations are idempotent.
	    channel.exchangeDeclare(DIRECT_EXCHANGE_NAME, BuiltinExchangeType.DIRECT, true);
        channel.queueDeclare(QUEUE, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueBind(QUEUE, DIRECT_EXCHANGE_NAME, DIRECT_ROUTING_KEY);
	}

    public void startProducingMessages() throws Exception {
        Thread thread = new Thread("RabbitmqProduce_Direct") {
            public void run() {
                try {
                    String message = "hello world";
                    Channel channel = createChannel();
                    init(channel);
                    channel.basicPublish(DIRECT_EXCHANGE_NAME, DIRECT_ROUTING_KEY, null, message.getBytes("UTF-8"));
                    System.out.println("[rabbitmq_direct] Published " + message);
                } catch (Exception e) {
                    System.out.println("[rabbitmq_direct] Unable to produce message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
    }

    public void startConsumingMessages() throws Exception {
        Thread thread = new Thread("RabbitmqConsume_Direct") {
            public void run() {
                try {
                    Channel channel = createChannel();
                    init(channel);
                    final Consumer consumer = createConsumer(channel, ThreadLocalRandom.current().nextInt(0, 200));
                    channel.basicConsume(QUEUE, /*autoAck=*/false, consumer);
                    System.out.println("[rabbitmq_direct] consumed messages");
                } catch (Exception e) {
                    System.out.println("[rabbitmq_direct] Unable to consume message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
    }
}
