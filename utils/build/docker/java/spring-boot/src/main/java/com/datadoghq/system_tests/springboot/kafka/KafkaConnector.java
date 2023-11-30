package com.datadoghq.system_tests.springboot.kafka;

import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;

import java.time.Duration;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

public class KafkaConnector {
    public static final String BOOTSTRAP_SERVERS = "kafka:9092";
    public static final String CONSUMER_GROUP = "testgroup1";
    public static final String DEFAULT_TOPIC = "DistributedTracing";
    public final String topic;

    public KafkaConnector(){
        this(DEFAULT_TOPIC);
    }

    public KafkaConnector(String topic){
        this.topic = topic;
    }

    private static KafkaTemplate<String, String> createKafkaTemplateForProducer() {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, BOOTSTRAP_SERVERS);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
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
                KafkaTemplate<String, String> kafkaTemplate = createKafkaTemplateForProducer();
                System.out.printf("Publishing message: %s%n", message);
                kafkaTemplate.send(topic, message);
            }
        };
        thread.start();
    }

    // Ideally we should be able to use @Component and @KafkaListener to auto consume messages, but I wasn't able
    // to get it to work. Can look into this as a follow up.
    public void startConsumingMessages() throws Exception {
        Thread thread = new Thread("KafkaConsume") {
            public void run() {
                KafkaConsumer<String, String> consumer = createKafkaConsumer();
                consumer.subscribe(Collections.singletonList(topic));
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(Long.MAX_VALUE));
                for (ConsumerRecord<String, String> record : records) {
                    System.out.println("got record! " + record.value() + " from " + record.topic());
                }
            }
        };
        thread.start();
        System.out.println("Started Kafka consumer thread");
    }

    // For APM testing, produce message without starting a new thread
    public void produceMessageWithoutNewThread(String message) throws Exception {
        KafkaTemplate<String, String> kafkaTemplate = createKafkaTemplateForProducer();
        System.out.printf("Publishing message: %s%n", message);
        kafkaTemplate.send(topic, message);
    }

    // For APM testing, a consume message without starting a new thread
    public void consumeMessageWithoutNewThread() throws Exception {
        KafkaConsumer<String, String> consumer = createKafkaConsumer();
        consumer.subscribe(Collections.singletonList(topic));
        ConsumerRecords<String, String> records = consumer.poll(Duration.ofSeconds(3));
        if(records.isEmpty())
            System.out.println("No record found when polling " + topic);
        for (ConsumerRecord<String, String> record : records) {
            System.out.println("got record! " + record.value() + " from " + record.topic());
        }
    }
}
