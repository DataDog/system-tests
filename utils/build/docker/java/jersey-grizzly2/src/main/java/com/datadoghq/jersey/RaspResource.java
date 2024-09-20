package com.datadoghq.jersey;

import static com.datadoghq.jersey.Main.DATA_SOURCE;

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

import java.io.File;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

@Path("/rasp")
@Produces(MediaType.TEXT_PLAIN)
public class RaspResource {

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
        return executeFli(file);
    }

    @POST
    @Path("/lfi")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    public String lfiPost(@FormParam("file") final String file) throws Exception {
        return executeFli(file);
    }

    @POST
    @Path("/lfi")
    @Consumes({MediaType.APPLICATION_XML, MediaType.APPLICATION_JSON} )
    public String lfiBody(final FileDTO file) throws Exception {
        return executeFli(file.getFile());
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

    private String executeFli(final String file) throws Exception {
        new File(file);
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
}
