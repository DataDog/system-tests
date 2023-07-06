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

public class RabbitmqConnector {
	private static final String DIRECT_EXCHANGE_NAME = "systemTestDirectExchange";
	private static final String DIRECT_ROUTING_KEY = "systemTestDirectRoutingKey";
	private static final String QUEUE = "systemTestRabbitmqQueue";


    private static Channel createChannel() throws Exception {
                ConnectionFactory connectionFactory = new ConnectionFactory();
                connectionFactory.setHost("rabbitmq");
                connectionFactory.setPort(5672);
                connectionFactory.setUsername("guest");
                connectionFactory.setPassword("guest");
                Connection connection = null;
                while (connection == null) {
                    try {
                        connection = connectionFactory.newConnection();
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                    if (connection == null) {
                        Thread.sleep(/*10s*/10000);
                    }
                }
                return connection.createChannel();
    }

    public void startProducingMessage(String message) throws Exception {
        Thread thread = new Thread("RabbitmqProduce") {
            public void run() {
                try {
                    Channel channel = createChannel();
                    channel.exchangeDeclare(DIRECT_EXCHANGE_NAME, BuiltinExchangeType.DIRECT, true);
                    channel.queueDeclare(QUEUE, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
                    channel.queueBind(QUEUE, DIRECT_EXCHANGE_NAME, DIRECT_ROUTING_KEY);
                    channel.basicPublish(DIRECT_EXCHANGE_NAME, DIRECT_ROUTING_KEY, null, message.getBytes("UTF-8"));
                    System.out.println("[rabbitmq] Published " + message);
                } catch (Exception e) {
                    System.out.println("[rabbitmq] Unable to produce message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
    }

	public static Consumer createConsumer(Channel channel, int failAfter) throws Exception {
		return new DefaultConsumer(channel) {

			@Override
			public void handleDelivery(String consumerTag,
									   Envelope envelope,
									   BasicProperties properties,
									   byte[] body) throws IOException{

				String message = new String(body, "UTF-8");
				System.out.println("[rabbitmq] Received '" + message + "'");

				long deliveryTag = envelope.getDeliveryTag();
				try {
					Thread.sleep(10);
				} catch (Exception e) {}
				channel.basicAck(deliveryTag, false);
			}
		};
	}

    public void startConsumingMessages() throws Exception {
        System.out.println("[rabbitmq] Start consuming messages");
        Thread thread = new Thread("RabbitmqConsume") {
            public void run() {
                try {
                    Channel channel = createChannel();

                    channel.exchangeDeclare(DIRECT_EXCHANGE_NAME, BuiltinExchangeType.DIRECT, true);
                    channel.queueDeclare(QUEUE, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
                    channel.queueBind(QUEUE, DIRECT_EXCHANGE_NAME, DIRECT_ROUTING_KEY);
                    System.out.println("[rabbitmq] Start consume-side bindings");

                    final Consumer consumer = createConsumer(channel, ThreadLocalRandom.current().nextInt(0, 200));
                    channel.basicConsume(QUEUE, /*autoAck=*/false, consumer);
                } catch (Exception e) {
                    System.out.println("[rabbitmq] Unable to consume message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
    }
}
