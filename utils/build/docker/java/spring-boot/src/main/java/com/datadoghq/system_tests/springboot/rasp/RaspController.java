package com.datadoghq.system_tests.springboot.rasp;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;
import static org.springframework.http.MediaType.APPLICATION_XML_VALUE;
import static org.springframework.web.bind.annotation.RequestMethod.GET;
import static org.springframework.web.bind.annotation.RequestMethod.POST;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

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
}
