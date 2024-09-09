package com.datadoghq.system_tests.springboot.rasp;

import static org.springframework.http.MediaType.APPLICATION_FORM_URLENCODED_VALUE;
import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;
import static org.springframework.http.MediaType.APPLICATION_XML_VALUE;
import static org.springframework.web.bind.annotation.RequestMethod.GET;
import static org.springframework.web.bind.annotation.RequestMethod.POST;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;

import javax.sql.DataSource;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.stream.Collectors;

@Controller
@RequestMapping("/rasp")
public class RaspController {

    private final DataSource dataSource;

    public RaspController(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @RequestMapping(value = "/sqli", method = {GET, POST})
    public ResponseEntity<String> sqli(@RequestParam("user_id") final String userId) throws SQLException {
        return execSql(userId);
    }

    @PostMapping(value = "/sqli", consumes = {APPLICATION_XML_VALUE, APPLICATION_JSON_VALUE})
    public ResponseEntity<String> sqli(@RequestBody final UserDTO body) throws SQLException {
        return execSql(body.getUserId());
    }

    @RequestMapping(value = "/ssrf", method = {GET, POST})
    public ResponseEntity<String> raspSSRF(@RequestParam(required = false, name="domain") String url) {
        String result = fakeHttpUrlConnect(url);
        return ResponseEntity.ok(result);
    }

    @PostMapping(value = "/ssrf", consumes = {APPLICATION_XML_VALUE, APPLICATION_JSON_VALUE})
    public ResponseEntity<String> raspSSRF(@RequestBody final DomainDTO body) {
        String result = fakeHttpUrlConnect(body.domain);
        return ResponseEntity.ok(result);
    }

    @SuppressWarnings({"SqlDialectInspection", "SqlNoDataSourceInspection"})
    private ResponseEntity<String> execSql(final String userId) throws SQLException {
        try (final Connection conn = dataSource.getConnection()) {
            final Statement stmt = conn.createStatement();
            final ResultSet set = stmt.executeQuery("SELECT * FROM users WHERE id='" + userId + "'");
            if (set.next()) {
                return ResponseEntity.ok("ID: " + set.getLong("ID"));
            }
        }
        return ResponseEntity.ok("User not found");
    }

    private String fakeHttpUrlConnect(String urlString) {
        try {
            URL url;
            try {
                url = new URL(urlString);
            } catch (MalformedURLException e) {
                url = new URL("http://" + urlString);
            }

            URLConnection connection = url.openConnection();
            connection.connect();
            return "OK";
        } catch (Exception e) {
            e.printStackTrace();
            return "http connection failed";
        }
    }

    @JacksonXmlRootElement(localName = "user_id")
    public static class UserDTO {
        @JsonProperty("user_id")
        @JacksonXmlText
        private String userId;

        public String getUserId() {
            return userId;
        }

        public void setUserId(String userId) {
            this.userId = userId;
        }
    }

    @JacksonXmlRootElement(localName = "domain")
    public static class DomainDTO {
        @JsonProperty("domain")
        @JacksonXmlText
        private String domain;

        public String getDomain() {
            return domain;
        }

        public void setDomain(String domain) {
            this.domain = domain;
        }
    }
}
