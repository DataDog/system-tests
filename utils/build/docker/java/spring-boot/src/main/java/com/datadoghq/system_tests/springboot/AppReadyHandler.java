package com.datadoghq.system_tests.springboot;

import com.datastax.oss.driver.api.core.CqlSession;
import com.mongodb.MongoClient;
import com.mongodb.client.MongoCollection;
import java.net.InetSocketAddress;
import java.util.concurrent.TimeUnit;
import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.SendResult;
import org.springframework.util.concurrent.ListenableFuture;
import org.springframework.util.concurrent.ListenableFutureCallback;
import org.springframework.stereotype.Component;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import java.util.Properties;
import java.time.Duration;

import java.util.HashMap;
import java.util.Map;
import java.io.StringWriter;
import java.io.PrintWriter;
import java.util.Arrays;

public class AppReadyHandler extends Thread{
  App app = null;

  AppReadyHandler(App app){
    this.app = app;
  }

  public void run(){
    init();
  }

  public void init() {
    System.out.println("Trying to start Kafka");
    //app.kafka = new KafkaConnector();
    //app.kafka.setup();
    System.out.println("Trying to start cassandra");
    app.cassandra = new CassandraConnector();
    app.cassandra.setup();
    System.out.println("Trying to start Mongo");
    initMongo();
    System.out.println("Initialized");
  }

  void initMongo() {
    app.mongoClient = new MongoClient("mongodb");
    MongoCollection<Document> collection = app.mongoClient.getDatabase("mydb").getCollection("test");

    collection.insertOne(new Document("name", "MongoDB")
        .append("id", 1)
        .append("title", "Skydiving is fun")
        .append("subject", "Have you ever thought about jumping off an airplane?"));
    collection.insertOne(new Document("name", "MongoDB")
        .append("id", 2)
        .append("title", "Mastering skydiving")
        .append("subject", "So jump in empty air, but many times"));
    collection.insertOne(new Document("name", "MongoDB")
        .append("id", 3)
        .append("title", "Wingsuit")
        .append("subject", "Flying like a bird made of cloth who just left a perfectly working airplane"));
  }
}

class KafkaConnector {
    private KafkaTemplate kafkaTemplate;

    public void setup() {
        ProducerFactory<String, String> producerFactory = KafkaHelper.producerFactory();
        this.kafkaTemplate = new KafkaTemplate<>(producerFactory);
        try {
            this.startConsumingMessages();
        } catch (Exception e) {
            System.out.println("Fail to set up consumer");
            e.printStackTrace();
        }
    }

    public void produceMessage(String message) throws Exception {
        Thread thread = new Thread("KafkaProduce") {
            public void run() {
                System.out.println(String.format("Publishing message: %s", message));
                kafkaTemplate.send("dsm-system-tests-queue", message);
            }
        };
        thread.start();
    }

    // Ideally we should be able to use @Component and @KafkaListener to auto consume messages, but I wasn't able
    // to get it to work. Can look into this as a follow up.
    public void startConsumingMessages() throws Exception {
        Thread thread = new Thread("KafkaConsume") {
            public void run() {
                Properties props = new Properties();
                props.setProperty("bootstrap.servers", "kafka:9092");
                props.setProperty("group.id", "testgroup1");
                props.setProperty("enable.auto.commit", "false");
                props.setProperty("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
                props.setProperty("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
                props.setProperty("auto.offset.reset", "earliest");
                KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
                consumer.subscribe(Arrays.asList("dsm-system-tests-queue"));
                while (true) {
                    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(Long.MAX_VALUE));
                    for (ConsumerRecord<String, String> record : records) {
                        System.out.println("got record! " + record.value() + " from " + record.topic());
                    }
                }
            }
        };
        thread.start();
        System.out.println("Started Kafka consumer sthread");
    }
}

class CassandraConnector {
  CqlSession session;

  public void setup() {
    boolean successInit = false;
    int retry = 1000;
    while (!successInit && retry-- > 0)
    {
      try {
        TimeUnit.MILLISECONDS.sleep(500);
        session = CqlSession.builder()
            .addContactPoint(new InetSocketAddress("cassandra", 9042))
            .withLocalDatacenter("datacenter1")
            .build();
        successInit = true;
      } catch (Exception ignored) {
      }
    }

    // Create KeySpace
    session.execute("CREATE KEYSPACE IF NOT EXISTS \"testDB\" WITH replication = {'class':'SimpleStrategy','replication_factor':1};");

    // Create table
    session.execute("USE \"testDB\";");
    session.execute("DROP TABLE IF EXISTS \"table\";");
    session.execute("CREATE TABLE \"table\" (id int PRIMARY KEY, title text, subject text);");

    // Insert data
    session.execute("INSERT INTO \"table\"(id, title, subject) VALUES (1, 'book1', 'subject1');");
    session.execute("INSERT INTO \"table\"(id, title, subject) VALUES (2, 'book2', 'subject2');");
    session.execute("INSERT INTO \"table\"(id, title, subject) VALUES (3, 'book3', 'subject3');");
    session.execute("INSERT INTO \"table\"(id, title, subject) VALUES (4, 'book4', 'subject4');");
  }

  public CqlSession getSession() {
    return this.session;
  }
}

class KafkaHelper {
    public static ProducerFactory<String, String> producerFactory() {
        Map<String, Object> configProps = new HashMap<>();

        configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
        configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);

        return new DefaultKafkaProducerFactory<>(configProps);
    }

    public ConsumerFactory<String, String> consumerFactory() {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
        configProps.put(ConsumerConfig.GROUP_ID_CONFIG, "dsm-system-tests-group");
        configProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        configProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        configProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");

        return new DefaultKafkaConsumerFactory<>(configProps);
    }

    public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, String> factory = new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());

        return factory;
    }
}
