package com.datadoghq.system_tests.springboot.rasp;

import com.datadoghq.system_tests.iast.utils.*;
import static org.springframework.http.MediaType.APPLICATION_FORM_URLENCODED_VALUE;
import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;
import static org.springframework.http.MediaType.APPLICATION_XML_VALUE;
import static org.springframework.web.bind.annotation.RequestMethod.GET;
import static org.springframework.web.bind.annotation.RequestMethod.POST;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlElementWrapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.io.File;

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
    private final CmdExamples cmdExamples;

    public RaspController(final DataSource dataSource) {
        this.dataSource = dataSource;
        this.cmdExamples = new CmdExamples();
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

    @RequestMapping(value = "/lfi", method = {GET, POST})
    public ResponseEntity<String> lfi(@RequestParam("file") final String file) {
        return execLfi(file);
    }

    @PostMapping(value = "/lfi", consumes = {APPLICATION_XML_VALUE, APPLICATION_JSON_VALUE})
    public ResponseEntity<String> lfi(@RequestBody final FileDTO body) throws Exception {
        return execLfi(body.getFile());
    }

    @RequestMapping(value = "/shi", method = {GET, POST})
    public ResponseEntity<String> shi(@RequestParam("list_dir") final String cmd) {
        return execShi(cmd);
    }

    @PostMapping(value = "/shi", consumes = {APPLICATION_XML_VALUE, APPLICATION_JSON_VALUE})
    public ResponseEntity<String> shi(@RequestBody final ListDirDTO body) throws Exception {
        return execShi(body.getCmd());
    }

    @RequestMapping(value = "/cmdi", method = {GET, POST})
    public ResponseEntity<String> cmdi(@RequestParam("command") final String[] arrayCmd) {
        return execCmdi(arrayCmd);
    }

    @PostMapping(value = "/cmdi", consumes = {APPLICATION_XML_VALUE, APPLICATION_JSON_VALUE})
    public ResponseEntity<String> cmdi(@RequestBody final CommandDTO body) throws Exception {
        return execCmdi(body.getCommand());
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

    private ResponseEntity<String> execLfi(final String file)  {
        new File(file);
        return ResponseEntity.ok("OK");
    }

    private ResponseEntity<String> execShi(final String cmd)  {
        cmdExamples.insecureCmd(cmd);
        return ResponseEntity.ok("OK");
    }

    private ResponseEntity<String> execCmdi(final String[] arrayCmd)  {
        cmdExamples.insecureCmd(arrayCmd);
        return ResponseEntity.ok("OK");
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

    @JacksonXmlRootElement(localName = "file")
    public static class FileDTO {
        @JsonProperty("file")
        @JacksonXmlText
        private String file;

        public String getFile() {
            return file;
        }

        public void setFile(String file) {
            this.file = file;
        }
    }

    @JacksonXmlRootElement(localName = "list_dir")
    public static class ListDirDTO {
        @JsonProperty("list_dir")
        @JacksonXmlText
        private String cmd;

        public String getCmd() {
            return cmd;
        }

        public void setCmd(String cmd) {
            this.cmd = cmd;
        }
    }

    @JacksonXmlRootElement(localName = "command")
    public static class CommandDTO {
        @JsonProperty("command")
        @JacksonXmlElementWrapper(useWrapping = false)
        @JacksonXmlProperty(localName = "cmd")
        private String[] command;

        public String[] getCommand() {
            return command;
        }

        public void setCommand(String[] command) {
            this.command = command;
        }
    }
}
