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

public class RabbitmqConnectorForFanoutExchange extends RabbitmqConnector {

	private static final String FANOUT_EXCHANGE_NAME = "systemTestFanoutExchange";
	private static final String FANOUT_EXCHANGE_QUEUE_1 = "systemTestRabbitmqFanoutQueue1";
	private static final String FANOUT_EXCHANGE_QUEUE_2 = "systemTestRabbitmqFanoutQueue2";
	private static final String FANOUT_EXCHANGE_QUEUE_3 = "systemTestRabbitmqFanoutQueue3";

	private void init(Channel channel) throws Exception {
	    // exchange and queue declarations are idempotent.
		channel.exchangeDeclare(FANOUT_EXCHANGE_NAME, BuiltinExchangeType.FANOUT, true);
        channel.queueDeclare(FANOUT_EXCHANGE_QUEUE_1, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueDeclare(FANOUT_EXCHANGE_QUEUE_2, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueDeclare(FANOUT_EXCHANGE_QUEUE_3, /*durable=*/true, /*exclusive=*/false, /*autoDelete=*/false, /*arguments=*/null);
        channel.queueBind(FANOUT_EXCHANGE_QUEUE_1, FANOUT_EXCHANGE_NAME, "");
        channel.queueBind(FANOUT_EXCHANGE_QUEUE_2, FANOUT_EXCHANGE_NAME, "");
        channel.queueBind(FANOUT_EXCHANGE_QUEUE_3, FANOUT_EXCHANGE_NAME, "");
	}

    public Thread startProducingMessages() throws Exception {
        Thread thread = new Thread("RabbitmqProduce_Fanout") {
            public void run() {
                String message = "hello world";
                try {
                    Channel channel = createChannel();
                    init(channel);
			        channel.basicPublish(FANOUT_EXCHANGE_NAME, "", null, message.getBytes("UTF-8"));
                    System.out.println("[rabbitmq_fanout] Published " + message);
                } catch (Exception e) {
                    System.out.println("[rabbitmq_fanout] Unable to produce message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
        return thread;
    }

    public Thread startConsumingMessages() throws Exception {
        Thread thread = new Thread("RabbitmqConsume_Fanout") {
            public void run() {
                try {
                    Channel channel = createChannel();
                    init(channel);
                    final Consumer consumer = createConsumer(channel, ThreadLocalRandom.current().nextInt(0, 200));
                    channel.basicConsume(FANOUT_EXCHANGE_QUEUE_1, /*autoAck=*/false, consumer);
                    channel.basicConsume(FANOUT_EXCHANGE_QUEUE_2, /*autoAck=*/false, consumer);
                    channel.basicConsume(FANOUT_EXCHANGE_QUEUE_3, /*autoAck=*/false, consumer);
                    System.out.println("[rabbitmq_fanout] consumed messages");
                } catch (Exception e) {
                    System.out.println("[rabbitmq_fanout] Unable to consume message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
        return thread;
    }
}
