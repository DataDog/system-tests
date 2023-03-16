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
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.SendResult;
import org.springframework.util.concurrent.ListenableFuture;
import org.springframework.util.concurrent.ListenableFutureCallback;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;
import java.io.StringWriter;
import java.io.PrintWriter;

public class AppReadyHandler extends Thread{
  App app = null;
  KafkaListenerEndpointRegistry kafkaListenerEndpointRegistry = null;

  AppReadyHandler(App app, KafkaListenerEndpointRegistry kafkaListenerEndpointRegistry){
    this.app = app;
    this.kafkaListenerEndpointRegistry = kafkaListenerEndpointRegistry;
  }

  public void run(){
    init();
  }

  public void init() {
    System.out.println("Trying to start Kafka");
    initKafka();
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

   void initKafka() {
    ProducerFactory<String, String> producerFactory = KafkaHelper.producerFactory();
    KafkaTemplate kafkaTemplate = new KafkaTemplate<>(producerFactory);
    app.kafkaProducer = new ProducerService(kafkaTemplate);

    boolean successInit = false;
    int retry = 20;
    while (!successInit && retry-- > 0)
    {
      try {
        TimeUnit.MILLISECONDS.sleep(2000);
        kafkaListenerEndpointRegistry.getListenerContainer("assigned_listener_id").start();
        successInit = true;
        System.out.println("Successfully started Kafka listener...");
      } catch (Exception ignored) {
        System.out.println("Awaiting kafka consumer setup...");
        StringWriter sw = new StringWriter();
        PrintWriter pw = new PrintWriter(sw);
        ignored.printStackTrace(pw);
        System.out.println(sw.toString());
      }
    }
    if (!successInit) {
        System.out.println("Kafka consumer setup failed");
    }
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

        return new DefaultKafkaConsumerFactory<>(configProps);
    }

    public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, String> factory = new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());

        return factory;
    }
}

class ProducerService {
    private static final Logger logger = LoggerFactory.getLogger(ProducerService.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public ProducerService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public String sendMessage(String message) throws Exception {
        System.out.println(String.format("Publishing message: %s", message));
        System.out.println(kafkaTemplate);
        logger.info(String.format("Publishing message: %s", message));
        ListenableFuture<SendResult<String, String>> future = this.kafkaTemplate.send("dsm-system-tests-queue", message);
        return future.get().toString();
    }
}

@Service
class ConsumerService {
    private static final Logger logger = LoggerFactory.getLogger(ConsumerService.class);

    public ConsumerService() {
        System.out.println("[HELLO] Creating Consumer");
    }

    @KafkaListener(
        id = "assigned_listener_id",
        topics = "dsm-system-tests-queue",
        groupId = "dsm-system-tests-group",
        autoStartup = "false")
    public void consume(String message) {
        System.out.println(String.format("Consumed message: %s", message));
        logger.info(String.format("Consumed message: %s", message));
    }
}