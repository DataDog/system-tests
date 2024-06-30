package com.datadoghq.vertx3.rasp;

import static io.vertx.core.http.HttpMethod.POST;

import io.netty.buffer.ByteBufInputStream;
import io.vertx.core.buffer.Buffer;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import io.vertx.ext.web.handler.BodyHandler;

import javax.sql.DataSource;
import javax.xml.bind.JAXBContext;
import javax.xml.bind.JAXBException;
import javax.xml.bind.Unmarshaller;
import javax.xml.bind.annotation.XmlAccessType;
import javax.xml.bind.annotation.XmlAccessorType;
import javax.xml.bind.annotation.XmlRootElement;
import javax.xml.bind.annotation.XmlValue;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.util.function.Consumer;

public class RaspRouteProvider implements Consumer<Router> {

    private static final String USER_ID = "user_id";

    private final DataSource dataSource;

    public RaspRouteProvider(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void accept(final Router router) {
        router.route("/rasp/*").method(POST).handler(BodyHandler.create());
        router.route().path("/rasp/sqli").consumes("application/xml").blockingHandler(rc -> executeSql(rc, parseXml(rc.getBody()).getUserId()));
        router.route().path("/rasp/sqli").consumes("application/json").blockingHandler(rc -> executeSql(rc, rc.getBodyAsJson().getString(USER_ID)));
        router.route().path("/rasp/sqli").blockingHandler(rc -> executeSql(rc, rc.request().getParam(USER_ID)));
    }

    @SuppressWarnings({"SqlDialectInspection", "SqlNoDataSourceInspection"})
    private void executeSql(final RoutingContext rc, final String userId) {
        try (final Connection conn = dataSource.getConnection()) {
            final CallableStatement stmt = conn.prepareCall("select * from user where username = '" + userId + "'");
            final ResultSet set = stmt.executeQuery();
            if (set.next()) {
                rc.response().end("ID: " + set.getLong("ID"));
            } else {
                rc.response().end("User not found");
            }
        } catch (final Throwable e) {
            rc.response().end(e.getMessage());
        }
    }

    private UserDTO parseXml(final Buffer buffer) {
        try {
            JAXBContext jc = JAXBContext.newInstance(UserDTO.class);
            Unmarshaller unmarshaller = jc.createUnmarshaller();
            return (UserDTO) unmarshaller.unmarshal(new ByteBufInputStream(buffer.getByteBuf()));
        } catch (JAXBException e) {
            throw new RuntimeException(e);
        }

    }

    @XmlRootElement(name = USER_ID)
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class UserDTO {

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
