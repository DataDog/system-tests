import io.opentracing.util.GlobalTracer;
import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.boot.context.event.*;
import org.springframework.context.event.*;

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
import java.util.stream.Collectors;

import io.opentracing.Span;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;



@RestController
@EnableAutoConfiguration
public class App {

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
        System.out.println("Initialized");
    }


    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

}
