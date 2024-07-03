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

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;

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

    @SuppressWarnings({"SqlDialectInspection", "SqlNoDataSourceInspection"})
    private String executeSql(final String userId) throws Exception {
        try (final Connection conn = DATA_SOURCE.getConnection()) {
            final CallableStatement stmt = conn.prepareCall("select * from user where username = '" + userId + "'");
            final ResultSet set = stmt.executeQuery();
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
}
