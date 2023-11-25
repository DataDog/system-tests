package com.datadoghq.system_tests.springboot.kafka;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.SendResult;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;

import java.io.StringWriter;
import java.io.PrintWriter;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

public class KafkaConnector {
    public static final String BOOTSTRAP_SERVERS = "kafka:9092";
    public static final String CONSUMER_GROUP = "testgroup1";
    public static final String TOPIC = "dsm-system-tests-queue";
    private KafkaTemplate<String, String> kafkaTemplate;
    private KafkaConsumer<String, String> consumer;

    public KafkaConnector() {
        kafkaTemplate = createKafkaTemplateForProducer();
        consumer = createKafkaConsumer();
    }

    private static KafkaTemplate<String, String> createKafkaTemplateForProducer() {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, BOOTSTRAP_SERVERS);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        // Refreshes metadata every 1 second
        props.put(ProducerConfig.METADATA_MAX_AGE_CONFIG, 1000);
        ProducerFactory<String, String> producerFactory = new DefaultKafkaProducerFactory<>(props);
        return new KafkaTemplate<String, String>(producerFactory);
    }

    private static KafkaConsumer<String, String> createKafkaConsumer() {
        Properties props = new Properties();
        props.setProperty("bootstrap.servers", BOOTSTRAP_SERVERS);
        props.setProperty("group.id", CONSUMER_GROUP);
        props.setProperty("enable.auto.commit", "false");
        props.setProperty("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        props.setProperty("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        props.setProperty("auto.offset.reset", "earliest");
        return new KafkaConsumer<String, String>(props);
    }

    public void startProducingMessage(String message) throws Exception {
        Thread thread = new Thread("KafkaProduce") {
            public void run() {
                System.out.println(String.format("Publishing message: %s", message));
                kafkaTemplate.send(TOPIC, message);
            }
        };
        kafkaTemplate.flush();
        Thread.sleep(1500);
        thread.start();
    }

    // Ideally we should be able to use @Component and @KafkaListener to auto consume messages, but I wasn't able
    // to get it to work. Can look into this as a follow up.
    public void startConsumingMessages() throws Exception {
        Thread thread = new Thread("KafkaConsume") {
            public void run() {
                consumer.subscribe(Arrays.asList(TOPIC));
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(Long.MAX_VALUE));
                for (ConsumerRecord<String, String> record : records) {
                    System.out.println("got record! " + record.value() + " from " + record.topic());
                }
            }
        };
        Thread.sleep(1500);
        thread.start();
        System.out.println("Started Kafka consumer thread");
    }
}
