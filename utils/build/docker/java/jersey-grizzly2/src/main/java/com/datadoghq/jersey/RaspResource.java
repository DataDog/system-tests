package com.datadoghq.jersey;

import static com.datadoghq.jersey.Main.DATA_SOURCE;

import com.datadoghq.system_tests.iast.utils.*;
import jakarta.json.bind.annotation.JsonbProperty;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;

import jakarta.xml.bind.annotation.XmlAccessType;
import jakarta.xml.bind.annotation.XmlAccessorType;
import jakarta.xml.bind.annotation.XmlRootElement;
import jakarta.xml.bind.annotation.XmlValue;
import jakarta.xml.bind.annotation.XmlElement;

import java.io.File;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

@Path("/rasp")
@Produces(MediaType.TEXT_PLAIN)
public class RaspResource {

    private final CmdExamples cmdExamples = new CmdExamples();

    @GET
    @Path("/sqli")
    public String sqliGet(@QueryParam("user_id") final String userId) throws Exception {
        return executeSql(userId);
    }

    @POST
    @Path("/sqli")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String sqliPost(@FormParam("user_id") final String userId) throws Exception {
        return executeSql(userId);
    }

    @POST
    @Path("/sqli")
    @Consumes({MediaType.APPLICATION_XML, MediaType.APPLICATION_JSON} )
    public String sqliBody(final UserDTO user) throws Exception {
        return executeSql(user.getUserId());
    }

    @GET
    @Path("/lfi")
    public String lfiGet(@QueryParam("file") final String file) throws Exception {
        return executeLfi(file);
    }

    @POST
    @Path("/lfi")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String lfiPost(@FormParam("file") final String file) throws Exception {
        return executeLfi(file);
    }

    @POST
    @Path("/lfi")
    @Consumes({MediaType.APPLICATION_XML, MediaType.APPLICATION_JSON} )
    public String lfiBody(final FileDTO file) throws Exception {
        return executeLfi(file.getFile());
    }

    @GET
    @Path("/ssrf")
    public String ssrfGet(@QueryParam("domain") final String domain) throws Exception {
        return executeUrl(domain);
    }

    @POST
    @Path("/ssrf")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String ssrfPost(@FormParam("domain") final String domain) throws Exception {
        return executeUrl(domain);
    }

    @POST
    @Path("/ssrf")
    @Consumes({MediaType.APPLICATION_XML, MediaType.APPLICATION_JSON} )
    public String ssrfBody(final DomainDTO domain) throws Exception {
        return executeUrl(domain.getDomain());
    }

    @GET
    @Path("/cmdi")
    public String cmdiGet(@QueryParam("command") final String[] command) throws Exception {
        return execCmdi(command);
    }

    @POST
    @Path("/cmdi")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String cmdiPost(@FormParam("command") final String[] command) throws Exception {
        return execCmdi(command);
    }

    @POST
    @Path("/cmdi")
    @Consumes({MediaType.APPLICATION_XML, MediaType.APPLICATION_JSON} )
    public String ssrfBody(final CommandDTO dto) throws Exception {
        return execCmdi(dto.getCommand());
    }

    @GET
    @Path("/shi")
    public String shiGet(@QueryParam("list_dir") final String command) throws Exception {
        return execShi(command);
    }

    @POST
    @Path("/shi")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String shiPost(@FormParam("list_dir") final String command) throws Exception {
        return execShi(command);
    }

    @POST
    @Path("/shi")
    @Consumes({MediaType.APPLICATION_XML, MediaType.APPLICATION_JSON} )
    public String shiBody(final ListDirDTO dto) throws Exception {
        return execShi(dto.getCmd());
    }

    @SuppressWarnings({"SqlDialectInspection", "SqlNoDataSourceInspection"})
    private String executeSql(final String userId) throws Exception {
        try (final Connection conn = DATA_SOURCE.getConnection()) {
            final Statement stmt = conn.createStatement();
            final ResultSet set = stmt.executeQuery("SELECT * FROM users WHERE id='" + userId + "'");
            if (set.next()) {
                return "ID: " + set.getLong("ID");
            } else {
                return "User not found";
            }
        }
    }

    @XmlRootElement(name = "user_id")
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class UserDTO {
        @JsonbProperty("user_id")
        @XmlValue
        private String userId;

        public String getUserId() {
            return userId;
        }

        public void setUserId(String userId) {
            this.userId = userId;
        }
    }

    private String executeLfi(final String file) throws Exception {
        new File(file);
        return "OK";
    }

    private String execShi(final String cmd)  {
        cmdExamples.insecureCmd(cmd);
        return "OK";
    }

    private String execCmdi(final String[] arrayCmd)  {
        cmdExamples.insecureCmd(arrayCmd);
        return "OK";
    }

    @XmlRootElement(name = "file")
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class FileDTO {
        @JsonbProperty("file")
        @XmlValue
        private String file;

        public String getFile() {
            return file;
        }

        public void setFile(String file) {
            this.file = file;
        }
    }

    private String executeUrl(String urlString) {
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


    @XmlRootElement(name = "domain")
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class DomainDTO {
        @JsonbProperty("domain")
        @XmlValue
        private String domain;

        public String getDomain() {
            return domain;
        }

        public void setDomain(String domain) {
            this.domain = domain;
        }
    }

    @XmlRootElement(name = "list_dir")
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class ListDirDTO {
        @JsonbProperty("list_dir")
        @XmlValue
        private String cmd;

        public String getCmd() {
            return cmd;
        }

        public void setCmd(String cmd) {
            this.cmd = cmd;
        }
    }

    @XmlRootElement(name = "command")
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class CommandDTO {
        @JsonbProperty("command")
        @XmlElement(name = "cmd")
        private String[] command;

        public String[] getCommand() {
            return command;
        }

        public void setCommand(String[] command) {
            this.command = command;
        }
    }


}
