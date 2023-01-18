package com.datadoghq.springbootnative;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.HttpURLConnection;
import java.net.URL;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
@RestController
public class IntegrationController {
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
}