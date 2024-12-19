package com.datadoghq.vertx3.rasp;

import static io.vertx.core.http.HttpMethod.POST;

import com.datadoghq.system_tests.iast.utils.CmdExamples;

import io.netty.buffer.ByteBufInputStream;
import io.vertx.core.buffer.Buffer;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import io.vertx.ext.web.handler.BodyHandler;

import java.io.File;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;

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
import java.sql.Statement;
import java.util.function.Consumer;

public class RaspRouteProvider implements Consumer<Router> {

    private static final String USER_ID = "user_id";

    private static final String FILE = "file";

    private static final String LIST_DIR = "list_dir";

    private static final String COMMAND = "command";

    private static final String DOMAIN = "domain";

    private final DataSource dataSource;

    private final CmdExamples cmdExamples;

    public RaspRouteProvider(final DataSource dataSource) {
        this.dataSource = dataSource;
        this.cmdExamples= new CmdExamples();
    }

    @Override
    public void accept(final Router router) {
        router.route("/rasp/*").method(POST).handler(BodyHandler.create());
        router.route().path("/rasp/sqli").consumes("application/xml").blockingHandler(rc -> executeSql(rc, parseXml(rc.getBody()).getUserId()));
        router.route().path("/rasp/sqli").consumes("application/json").blockingHandler(rc -> executeSql(rc, rc.getBodyAsJson().getString(USER_ID)));
        router.route().path("/rasp/sqli").blockingHandler(rc -> executeSql(rc, rc.request().getParam(USER_ID)));
        router.route().path("/rasp/lfi").consumes("application/xml").blockingHandler(rc -> executeLfi(rc, parseFileXml(rc.getBody()).getFile()));
        router.route().path("/rasp/lfi").consumes("application/json").blockingHandler(rc -> executeLfi(rc, rc.getBodyAsJson().getString(FILE)));
        router.route().path("/rasp/lfi").blockingHandler(rc -> executeLfi(rc, rc.request().getParam(FILE)));
        router.route().path("/rasp/shi").consumes("application/xml").blockingHandler(rc -> executeShi(rc, parseListDirXml(rc.getBody()).getCmd()));
        router.route().path("/rasp/shi").consumes("application/json").blockingHandler(rc -> executeShi(rc, rc.getBodyAsJson().getString(LIST_DIR)));
        router.route().path("/rasp/shi").blockingHandler(rc -> executeShi(rc, rc.request().getParam(LIST_DIR)));
        router.route().path("/rasp/cmdi").consumes("application/xml").blockingHandler(rc -> executeCmdi(rc, parseCommandXml(rc.getBody()).getCommand()));
        router.route().path("/rasp/cmdi").consumes("application/json").blockingHandler(rc -> {
            var jsonArray = rc.getBodyAsJson().getJsonArray(COMMAND);
            String[] commandArray = jsonArray.stream()
                    .map(Object::toString)
                    .toArray(String[]::new);
            executeCmdi(rc, commandArray);
        });
        router.route().path("/rasp/cmdi").blockingHandler(rc -> {
            String[] commandArray = rc.request().getParam(COMMAND).split(",");
            executeCmdi(rc, commandArray);
        });
        router.route().path("/rasp/ssrf").consumes("application/xml").blockingHandler(rc -> executeUrl(rc, parseDomainXml(rc.getBody()).getDomain()));
        router.route().path("/rasp/ssrf").consumes("application/json").blockingHandler(rc -> executeUrl(rc, rc.getBodyAsJson().getString(FILE)));
        router.route().path("/rasp/ssrf").blockingHandler(rc -> executeUrl(rc, rc.request().getParam(FILE)));
    }

    @SuppressWarnings({"SqlDialectInspection", "SqlNoDataSourceInspection"})
    private void executeSql(final RoutingContext rc, final String userId) {
        try (final Connection conn = dataSource.getConnection()) {
            final Statement stmt = conn.createStatement();
            final ResultSet set = stmt.executeQuery("SELECT * FROM users WHERE id='" + userId + "'");
            if (set.next()) {
                rc.response().end("ID: " + set.getLong("ID"));
            } else {
                rc.response().end("User not found");
            }
        } catch (final Throwable e) {
            rc.response().end(e.getMessage());
        }
    }

    private void executeLfi(final RoutingContext rc, final String file) {
        new File(file);
        rc.response().end("OK");
    }

    private void executeShi(final RoutingContext rc, final String cmd) {
        cmdExamples.insecureCmd(cmd);
        rc.response().end("OK");
    }

    private void executeCmdi(final RoutingContext rc, final String[] arrayCmd) {
        cmdExamples.insecureCmd(arrayCmd);
        rc.response().end("OK");
    }



    private static void executeUrl(final RoutingContext rc, String urlString) {
        try {
            URL url;
            try {
                url = new URL(urlString);
            } catch (MalformedURLException e) {
                url = new URL("http://" + urlString);
            }

            URLConnection connection = url.openConnection();
            connection.connect();
            rc.response().end("OK");
        } catch (Exception e) {
            e.printStackTrace();
            rc.response().end("http connection failed");
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

    private FileDTO parseFileXml(final Buffer buffer) {
        try {
            JAXBContext jc = JAXBContext.newInstance(FileDTO.class);
            Unmarshaller unmarshaller = jc.createUnmarshaller();
            return (FileDTO) unmarshaller.unmarshal(new ByteBufInputStream(buffer.getByteBuf()));
        } catch (JAXBException e) {
            throw new RuntimeException(e);
        }
    }

    private ListDirDTO parseListDirXml(final Buffer buffer) {
        try {
            JAXBContext jc = JAXBContext.newInstance(ListDirDTO.class);
            Unmarshaller unmarshaller = jc.createUnmarshaller();
            return (ListDirDTO) unmarshaller.unmarshal(new ByteBufInputStream(buffer.getByteBuf()));
        } catch (JAXBException e) {
            throw new RuntimeException(e);
        }
    }

    private CommandDTO parseCommandXml(final Buffer buffer) {
        try {
            JAXBContext jc = JAXBContext.newInstance(CommandDTO.class);
            Unmarshaller unmarshaller = jc.createUnmarshaller();
            return (CommandDTO) unmarshaller.unmarshal(new ByteBufInputStream(buffer.getByteBuf()));
        } catch (JAXBException e) {
            throw new RuntimeException(e);
        }
    }

    private DomainDTO parseDomainXml(final Buffer buffer) {
        try {
            JAXBContext jc = JAXBContext.newInstance(DomainDTO.class);
            Unmarshaller unmarshaller = jc.createUnmarshaller();
            return (DomainDTO) unmarshaller.unmarshal(new ByteBufInputStream(buffer.getByteBuf()));
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

    @XmlRootElement(name = FILE)
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class FileDTO {

        @XmlValue
        private String file;

        public String getFile() {
            return file;
        }

        public void setFile(String file) {
            this.file = file;
        }
    }

    @XmlRootElement(name = DOMAIN)
    @XmlAccessorType(XmlAccessType.FIELD)
    public static class DomainDTO {

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
        private String[] command;

        public String[] getCommand() {
            return command;
        }

        public void setCommand(String[] command) {
            this.command = command;
        }
    }
}
