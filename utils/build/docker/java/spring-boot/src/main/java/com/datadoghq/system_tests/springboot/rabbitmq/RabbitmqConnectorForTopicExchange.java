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

public class RabbitmqConnectorForTopicExchange extends RabbitmqConnector {

	private static final String TOPIC_EXCHANGE_NAME = "systemTestTopicExchange";
	private static final String TOPIC_EXCHANGE_QUEUE_1 = "systemTestRabbitmqTopicQueue1";
	private static final String TOPIC_EXCHANGE_QUEUE_2 = "systemTestRabbitmqTopicQueue2";
	private static final String TOPIC_EXCHANGE_QUEUE_3 = "systemTestRabbitmqTopicQueue3";

	private void init(Channel channel) throws Exception {
	    // exchange and queue declarations are idempotent.
        channel.exchangeDeclare(TOPIC_EXCHANGE_NAME, BuiltinExchangeType.TOPIC, true);
        channel.queueDeclare(TOPIC_EXCHANGE_QUEUE_1, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueDeclare(TOPIC_EXCHANGE_QUEUE_2, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueDeclare(TOPIC_EXCHANGE_QUEUE_3, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueBind(TOPIC_EXCHANGE_QUEUE_1, TOPIC_EXCHANGE_NAME, "test.topic.*.cake");
        channel.queueBind(TOPIC_EXCHANGE_QUEUE_2, TOPIC_EXCHANGE_NAME, "test.topic.vanilla.*");
        channel.queueBind(TOPIC_EXCHANGE_QUEUE_3, TOPIC_EXCHANGE_NAME, "test.topic.chocolate.*");
	}

    public Thread startProducingMessages() throws Exception {
        Thread thread = new Thread("RabbitmqProduce_Topic") {
            public void run() {
                String message = "hello world";
                try {
                    Channel channel = createChannel();
                    init(channel);
                    channel.basicPublish(TOPIC_EXCHANGE_NAME, "test.topic.chocolate.cake", null, message.getBytes("UTF-8"));
                    channel.basicPublish(TOPIC_EXCHANGE_NAME, "test.topic.chocolate.icecream", null, message.getBytes("UTF-8"));
                    channel.basicPublish(TOPIC_EXCHANGE_NAME, "test.topic.vanilla.icecream", null, message.getBytes("UTF-8"));
                    System.out.println("[rabbitmq_topic] Published " + message);
                } catch (Exception e) {
                    System.out.println("[rabbitmq_topic] Unable to produce message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
        return thread;
    }

    public Thread startConsumingMessages() throws Exception {
        Thread thread = new Thread("RabbitmqConsume_Topic") {
            public void run() {
                try {
                    Channel channel = createChannel();
                    init(channel);
                    final Consumer consumer = createConsumer(channel, ThreadLocalRandom.current().nextInt(0, 200));
                    channel.basicConsume(TOPIC_EXCHANGE_QUEUE_1, /*autoAck=*/false, consumer);
                    channel.basicConsume(TOPIC_EXCHANGE_QUEUE_2, /*autoAck=*/false, consumer);
                    channel.basicConsume(TOPIC_EXCHANGE_QUEUE_3, /*autoAck=*/false, consumer);
                    System.out.println("[rabbitmq_topic] consumed messages");
                } catch (Exception e) {
                    System.out.println("[rabbitmq_topic] Unable to consume message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
        return thread;
    }
}
