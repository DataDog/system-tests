package com.datadoghq.system_tests.springboot.rabbitmq;

import com.rabbitmq.client.BuiltinExchangeType;
import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.StringWriter;
import java.io.PrintWriter;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

public class RabbitmqConnector {
	private final static String DIRECT_EXCHANGE_NAME = "systemTestDirectExchange";
	private final static String DIRECT_ROUTING_KEY = "systemTestDirectRoutingKey";


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
                    channel.basicPublish(DIRECT_EXCHANGE_NAME, DIRECT_ROUTING_KEY, null, message.getBytes("UTF-8"));
                    System.out.println("Published " + message);
                } catch (Exception e) {
                    System.out.println("Unable to produce message");
                    e.printStackTrace();
                }
            }
        };
        thread.start();
    }
/*
    // Ideally we should be able to use @Component and @KafkaListener to auto consume messages, but I wasn't able
    // to get it to work. Can look into this as a follow up.
    public void startConsumingMessages() throws Exception {
        Thread thread = new Thread("KafkaConsume") {
            public void run() {
                KafkaConsumer<String, String> consumer = createKafkaConsumer();
                consumer.subscribe(Arrays.asList(TOPIC));
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(Long.MAX_VALUE));
                for (ConsumerRecord<String, String> record : records) {
                    System.out.println("got record! " + record.value() + " from " + record.topic());
                }
            }
        };
        thread.start();
        System.out.println("Started Kafka consumer thread");
    }*/
}
