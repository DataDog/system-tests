package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.grpc.WebLogInterface;
import com.datadoghq.system_tests.springboot.grpc.SynchronousWebLogGrpc;
import com.datastax.oss.driver.api.core.CqlSession;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.mongodb.MongoClient;
import com.mongodb.client.MongoCollection;
import datadog.trace.api.Trace;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import ognl.Ognl;
import ognl.OgnlException;
import org.bson.Document;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.event.EventListener;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletResponse;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.MalformedURLException;
import java.net.URL;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import static com.mongodb.client.model.Filters.eq;


@RestController
@EnableAutoConfiguration
@ComponentScan(basePackages = {"com.datadoghq.system_tests.springboot"})
public class App {

    CassandraConnector cassandra;
    MongoClient mongoClient;

    @RequestMapping("/")
    String home() {
        return "Hello World!";
    }

    @GetMapping("/headers")
    String headers(HttpServletResponse response) {
        response.setHeader("content-language", "en-US");
        return "012345678901234567890123456789012345678901";
    }

    @GetMapping("/waf/**")
    String waf() {
        return "Hello World!";
    }

    @PostMapping(value = "/waf",
            consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    String postWafUrlencoded(@RequestParam MultiValueMap<String, String> body) {
        return body.toString();
    }

    @PostMapping(value = "/waf",
            consumes = MediaType.APPLICATION_JSON_VALUE)
    String postWafJson(@RequestBody Object body) {
        return body.toString();
    }

    @PostMapping(value = "/waf", consumes = MediaType.APPLICATION_XML_VALUE)
    String postWafXml(@RequestBody XmlObject object) {
        return object.toString();
    }

    @RequestMapping("/status")
    ResponseEntity<String> status(@RequestParam Integer code) {
        return new ResponseEntity<>(HttpStatus.valueOf(code));
    }

    @JacksonXmlRootElement
    public static class XmlObject {
        public XmlObject() {}
        public XmlObject(String value) { this.value = value; }

        @JacksonXmlText
        public String value;

        @JacksonXmlProperty
        public String attack;

        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder("AElement{");
            sb.append("value='").append(value).append('\'');
            sb.append(", attack='").append(attack).append('\'');
            sb.append('}');
            return sb.toString();
        }
    }

    @RequestMapping("/sample_rate_route/{i}")
    String sample_route(@PathVariable("i") String i) {
        return "OK";
    }

    @RequestMapping("/params/{str}")
    String params_route(@PathVariable("str") String str) {
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
        new AppReadyHandler(this).start();
    }



 //   @Bean
 //   SynchronousWebLogGrpc synchronousGreeter(WebLogInterface localInterface) {
 //       return new SynchronousWebLogGrpc(localInterface.getPort());
  //  }

  //  @Bean
  //  WebLogInterface localInterface() throws IOException {
  //      return new WebLogInterface();
  //  }

    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

}
