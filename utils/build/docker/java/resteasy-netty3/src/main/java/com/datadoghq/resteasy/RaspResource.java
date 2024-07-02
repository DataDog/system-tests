package com.datadoghq.resteasy;

import static com.datadoghq.resteasy.Main.DATA_SOURCE;

import com.fasterxml.jackson.annotation.JsonProperty;

import javax.ws.rs.Consumes;
import javax.ws.rs.FormParam;
import javax.ws.rs.GET;
import javax.ws.rs.POST;
import javax.ws.rs.Path;
import javax.ws.rs.Produces;
import javax.ws.rs.QueryParam;
import javax.ws.rs.core.MediaType;
import javax.xml.bind.annotation.XmlAccessType;
import javax.xml.bind.annotation.XmlAccessorType;
import javax.xml.bind.annotation.XmlRootElement;
import javax.xml.bind.annotation.XmlValue;
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
        @JsonProperty("user_id")
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
