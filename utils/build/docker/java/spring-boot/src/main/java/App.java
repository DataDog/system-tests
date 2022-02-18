import com.datastax.driver.core.Cluster;
import com.datastax.driver.core.Session;
import com.mongodb.client.MongoCollection;
import ognl.Ognl;
import io.opentracing.util.GlobalTracer;
import ognl.OgnlException;
import org.bson.Document;
import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.boot.context.event.*;
import org.springframework.context.event.*;
import com.mongodb.MongoClient;

import datadog.trace.api.Trace;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import java.util.concurrent.TimeUnit;

import io.opentracing.Span;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static com.mongodb.client.model.Filters.eq;


@RestController
@EnableAutoConfiguration
public class App {

    CassandraConnector cassandra;
    MongoClient mongoClient;

    @RequestMapping("/")
    String home() {
        return "Hello World!";
    }

    @RequestMapping("/waf/**")
    String waf() {
        return "Hello World!";
    }

    @RequestMapping("/sample_rate_route/{i}")
    String sample_route(@PathVariable("i") String i) {
        return "OK";
    }

    @RequestMapping("/trace/sql")
    String traceSQL() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        // NOTE: see README.md for setting up the docker image to quickly test this

        String url = "jdbc:postgresql://postgres_db/sportsdb?user=postgres&password=postgres";
        try (Connection pgConn = DriverManager.getConnection(url)) {

            Statement st = pgConn.createStatement();
            ResultSet rs = st.executeQuery("SELECT * FROM display_names LIMIT 10");
            while (rs.next())
            {
                System.out.print("Column 2 returned ");
                System.out.println(rs.getString(2));
            }
            rs.close();
            st.close();
        } catch (SQLException e) {
            e.printStackTrace(System.err);
            return "pgsql exception :(";
        }

        return "hi SQL";
    }

    @RequestMapping("/trace/http")
    String traceHTTP() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        try {
            URL server = new URL("http://example.com");
            HttpURLConnection connection = (HttpURLConnection)server.openConnection();
            connection.connect();
            System.out.println("Response code:" + connection.getResponseCode());
        } catch (Exception e) {
            e.printStackTrace(System.err);
            return "ssrf exception :(";
        }
        return "hi HTTP";
    }

    @RequestMapping("/trace/cassandra")
    String traceCassandra() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        cassandra.getSession().execute("SELECT * FROM \"table\" WHERE id = 1").all();

        return "hi Cassandra";
    }

    @RequestMapping("/trace/mongo")
    String traceMongo() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        MongoCollection<Document> collection = mongoClient.getDatabase("mydb").getCollection("test");
        Document doc = collection.find(eq("id", 3)).first();
        if (doc != null) {
            return "hi Mongo, " + doc.get("subject").toString();
        }
        return "hi Mongo";
    }

    @RequestMapping("/trace/ognl")
    String traceOGNL() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        List<String> list = Arrays.asList("Have you ever thought about jumping off an airplane?",
                "Flying like a bird made of cloth who just left a perfectly working airplane");
        try {
            Object expr = Ognl.parseExpression("[1]");
            String value = (String) Ognl.getValue(expr, list);
            return "hi OGNL, " + value;
        } catch (OgnlException e) {
            e.printStackTrace();
        }

        return "hi OGNL";
    }

    // E.g. curl "http://localhost:8080/sqli?q=%271%27%20union%20select%20%2A%20from%20display_names"
    @RequestMapping("/rasp/sqli")
    String raspSQLi(@RequestParam(required = false, name="q") String param) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        // NOTE: see README.md for setting up the docker image to quickly test this
        String url = "jdbc:postgresql://postgres_db/sportsdb?user=postgres&password=postgres";
        try (Connection pgConn = DriverManager.getConnection(url)) {
            String query = "SELECT * FROM display_names WHERE full_name = ";
            Statement st = pgConn.createStatement();
            ResultSet rs = st.executeQuery(query + param);

            int i = 0;
            while (rs.next()) {
                i++;
            }
            System.out.printf("Read %d rows", i);
            rs.close();
            st.close();
        } catch (SQLException e) {
            e.printStackTrace(System.err);
            return "pgsql exception :(";
        }

        return "Done SQL injection with param: " + param;
    }

    @RequestMapping("/rasp/ssrf")
    String raspSSRF(@RequestParam(required = false, name="url") String url) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        try {
            URL server;
            try {
                server = new URL(url);
            } catch (MalformedURLException e) {
                server = new URL("http://" + url);
            }

            HttpURLConnection connection = (HttpURLConnection)server.openConnection();
            connection.connect();
            System.out.println("Response code:" + connection.getResponseCode());
            System.out.println("Response message:" + connection.getResponseMessage());
            InputStream test = connection.getErrorStream();
            String result = new BufferedReader(new InputStreamReader(test)).lines().collect(Collectors.joining("\n"));
            return result;
        } catch (Exception e) {
            e.printStackTrace(System.err);
            return "ssrf exception :(";
        }
    }

    @EventListener(ApplicationReadyEvent.class)
    @Trace
    public void init() {
        cassandra = new CassandraConnector();
        cassandra.setup();
        initMongo();
        System.out.println("Initialized");
    }

    void initMongo() {
        mongoClient = new MongoClient("127.0.0.1");
        MongoCollection<Document> collection = mongoClient.getDatabase("mydb").getCollection("test");

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

    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

}

class CassandraConnector {
    private Cluster cluster;
    private Session session;

    public void setup() {
        Cluster.Builder b = Cluster.builder().addContactPoint("cassandra");

        boolean successInit = false;
        int retry = 1000;
        while (!successInit && retry-- > 0)
        {
            try {
                TimeUnit.MILLISECONDS.sleep(500);
                cluster = b.build();
                session = cluster.connect();
                successInit = true;

            } catch (Exception e) {
                cluster.close();
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

    public Session getSession() {
        return this.session;
    }

    public void close() {
        session.close();
        cluster.close();
    }
}