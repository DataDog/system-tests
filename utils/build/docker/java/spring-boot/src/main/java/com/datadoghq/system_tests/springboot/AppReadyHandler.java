package com.datadoghq.system_tests.springboot;

import com.datastax.oss.driver.api.core.CqlSession;
import com.mongodb.MongoClient;
import com.mongodb.client.MongoCollection;
import java.net.InetSocketAddress;
import java.util.concurrent.TimeUnit;
import org.bson.Document;

public class AppReadyHandler extends Thread{
  App app = null;

  AppReadyHandler(App app){
    this.app = app;
  }

  public void run(){
    init();
  }

  public void init() {
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