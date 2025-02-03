package com.datadoghq.ratpack;


import static com.datadoghq.ratpack.Main.DATA_SOURCE;
import static ratpack.jackson.Jackson.fromJson;

import com.datadoghq.system_tests.iast.utils.CmdExamples;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlElementWrapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.google.common.reflect.TypeToken;
import ratpack.form.Form;
import ratpack.handling.Chain;
import ratpack.handling.Context;
import ratpack.handling.Handler;
import ratpack.http.HttpMethod;
import ratpack.http.MediaType;
import ratpack.http.Status;
import ratpack.http.TypedData;
import ratpack.parse.Parse;
import ratpack.parse.ParserSupport;
import ratpack.registry.Registry;

import java.io.File;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

public class RaspHandlers {

    private static CmdExamples cmdExamples = new CmdExamples();

    public void setup(Chain chain) {
        chain.path("rasp/sqli", new Handler() {
            @Override
            public void handle(final Context ctx) throws Exception {
                MediaType contentType = ctx.getRequest().getContentType();
                if (ctx.getRequest().getMethod() == HttpMethod.GET) {
                    ctx.insert(QueryHandler.INSTANCE);
                } else if (contentType.isForm()) {
                    ctx.insert(FormHandler.INSTANCE);
                } else if (contentType.isJson()) {
                    ctx.insert(JsonHandler.INSTANCE);
                } else if (contentType.getType().equals("application/xml") || contentType.getType().equals("text/xml")) {
                    ctx.insert(Registry.single(XmlParser.INSTANCE), XmlHandler.INSTANCE);
                } else {
                    ctx.getResponse().status(Status.BAD_REQUEST);
                }
            }
        });
        chain.path("rasp/lfi", new Handler() {
            @Override
            public void handle(final Context ctx) throws Exception {
                MediaType contentType = ctx.getRequest().getContentType();
                if (ctx.getRequest().getMethod() == HttpMethod.GET) {
                    ctx.insert(QueryLfiHandler.INSTANCE);
                } else if (contentType.isForm()) {
                    ctx.insert(FormLfiHandler.INSTANCE);
                } else if (contentType.isJson()) {
                    ctx.insert(JsonLfiHandler.INSTANCE);
                } else if (contentType.getType().equals("application/xml") || contentType.getType().equals("text/xml")) {
                    ctx.insert(Registry.single(XmlParser.INSTANCE), XmlLfiHandler.INSTANCE);
                } else {
                    ctx.getResponse().status(Status.BAD_REQUEST);
                }
            }
        });
        chain.path("rasp/ssrf", new Handler() {
            @Override
            public void handle(final Context ctx) throws Exception {
                MediaType contentType = ctx.getRequest().getContentType();
                if (ctx.getRequest().getMethod() == HttpMethod.GET) {
                    ctx.insert(QuerySsrfHandler.INSTANCE);
                } else if (contentType.isForm()) {
                    ctx.insert(FormSsrfHandler.INSTANCE);
                } else if (contentType.isJson()) {
                    ctx.insert(JsonSsrfHandler.INSTANCE);
                } else if (contentType.getType().equals("application/xml") || contentType.getType().equals("text/xml")) {
                    ctx.insert(Registry.single(XmlParser.INSTANCE), XmlSsrfHandler.INSTANCE);
                } else {
                    ctx.getResponse().status(Status.BAD_REQUEST);
                }
            }
        });
        chain.path("rasp/shi", new Handler() {
            @Override
            public void handle(final Context ctx) throws Exception {
                MediaType contentType = ctx.getRequest().getContentType();
                if (ctx.getRequest().getMethod() == HttpMethod.GET) {
                    ctx.insert(QueryShiHandler.INSTANCE);
                } else if (contentType.isForm()) {
                    ctx.insert(FormShiHandler.INSTANCE);
                } else if (contentType.isJson()) {
                    ctx.insert(JsonShiHandler.INSTANCE);
                } else if (contentType.getType().equals("application/xml") || contentType.getType().equals("text/xml")) {
                    ctx.insert(Registry.single(XmlParser.INSTANCE), XmlShiHandler.INSTANCE);
                } else {
                    ctx.getResponse().status(Status.BAD_REQUEST);
                }
            }
        });
        chain.path("rasp/cmdi", new Handler() {
            @Override
            public void handle(final Context ctx) throws Exception {
                MediaType contentType = ctx.getRequest().getContentType();
                if (ctx.getRequest().getMethod() == HttpMethod.GET) {
                    ctx.insert(QueryCmdiHandler.INSTANCE);
                } else if (contentType.isForm()) {
                    ctx.insert(FormCmdiHandler.INSTANCE);
                } else if (contentType.isJson()) {
                    ctx.insert(JsonCmdiHandler.INSTANCE);
                } else if (contentType.getType().equals("application/xml") || contentType.getType().equals("text/xml")) {
                    ctx.insert(Registry.single(XmlParser.INSTANCE), XmlCmdiHandler.INSTANCE);
                } else {
                    ctx.getResponse().status(Status.BAD_REQUEST);
                }
            }
        });
    }

    enum FormHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var form = ctx.parse(Form.class);
            form.then(f -> executeSql(ctx, f.get("user_id")));
        }
    }

    enum FormLfiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var form = ctx.parse(Form.class);
            form.then(f -> executeLfi(ctx, f.get("file")));
        }
    }

    enum FormShiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var form = ctx.parse(Form.class);
            form.then(f -> executeShi(ctx, f.get("list_dir")));
        }
    }

    enum FormCmdiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var form = ctx.parse(Form.class);
            form.then(f -> {
                String[] commandArray = f.get("command").split(",");
                executeCmdi(ctx, commandArray);
            });
        }
    }

    enum FormSsrfHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var form = ctx.parse(Form.class);
            form.then(f -> executeUrl(ctx, f.get("domain")));
        }
    }

    enum JsonHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var obj = ctx.parse(fromJson(UserDTO.class));
            obj.then(user -> executeSql(ctx, user.getUserId()));
        }
    }

    enum JsonLfiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var obj = ctx.parse(fromJson(FileDTO.class));
            obj.then(file -> executeLfi(ctx, file.getFile()));
        }
    }

    enum JsonShiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var obj = ctx.parse(fromJson(ListDirDTO.class));
            obj.then(cmd -> executeShi(ctx, cmd.getCmd()));
        }
    }

    enum JsonCmdiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var obj = ctx.parse(fromJson(CommandDTO.class));
            obj.then(command -> executeCmdi(ctx, command.getCommand()));
        }
    }

    enum JsonSsrfHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var obj = ctx.parse(fromJson(DomainDTO.class));
            obj.then(domain -> executeUrl(ctx, domain.getDomain()));
        }
    }

    static class XmlParser extends ParserSupport<Void> {
        final static XmlParser INSTANCE = new XmlParser();

        static final XmlMapper XML_MAPPER = new XmlMapper();

        @Override
        public <T> T parse(Context context, TypedData requestBody, Parse<T, Void> parse) throws Exception {
            return XML_MAPPER.readValue(requestBody.getInputStream(), toJavaType(parse.getType()));
        }

        private static <T> JavaType toJavaType(TypeToken<T> type) {
            return XML_MAPPER.getTypeFactory().constructType(type.getType());
        }
    }

    enum XmlHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var xml = ctx.parse(Parse.of(UserDTO.class));
            xml.then(user -> executeSql(ctx, user.getUserId()));
        }
    }

    enum XmlLfiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var xml = ctx.parse(Parse.of(FileDTO.class));
            xml.then(file -> executeLfi(ctx, file.getFile()));
        }
    }

    enum XmlShiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var xml = ctx.parse(Parse.of(ListDirDTO.class));
            xml.then(cmd -> executeShi(ctx, cmd.getCmd()));
        }
    }

    enum XmlCmdiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var xml = ctx.parse(Parse.of(CommandDTO.class));
            xml.then(command -> executeCmdi(ctx, command.getCommand()));
        }
    }

    enum XmlSsrfHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var xml = ctx.parse(Parse.of(DomainDTO.class));
            xml.then(domain -> executeUrl(ctx, domain.getDomain()));
        }
    }

    enum QueryHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var userId = ctx.getRequest().getQueryParams().get("user_id");
            executeSql(ctx, userId);
        }
    }

    enum QueryLfiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var file = ctx.getRequest().getQueryParams().get("file");
            executeLfi(ctx, file);
        }
    }

    enum QueryShiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var cmd = ctx.getRequest().getQueryParams().get("list_dir");
            executeShi(ctx, cmd);
        }
    }

    enum QueryCmdiHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var command = ctx.getRequest().getQueryParams().get("command");
            String[] commandArray = command.split(",");
            executeCmdi(ctx, commandArray);
        }
    }

    enum QuerySsrfHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var domain = ctx.getRequest().getQueryParams().get("domain");
            executeUrl(ctx, domain);
        }
    }

    @SuppressWarnings({"SqlDialectInspection", "SqlNoDataSourceInspection"})
    private static void executeSql(final Context ctx, final String userId) throws Exception {
        try (final Connection conn = DATA_SOURCE.getConnection()) {
            final Statement stmt = conn.createStatement();
            final ResultSet set = stmt.executeQuery("SELECT * FROM users WHERE id='" + userId + "'");
            if (set.next()) {
                ctx.getResponse().send("text/plain", "ID: " + set.getLong("ID"));
            } else {
                ctx.getResponse().send("text/plain", "User not found");
            }
        }
    }

    private static void executeLfi(final Context ctx, final String file) {
        new File(file);
        ctx.getResponse().send("text/plain", "OK");
    }

    private static void executeShi(final Context ctx, final String cmd) {
        cmdExamples.insecureCmd(cmd);
        ctx.getResponse().send("text/plain", "OK");
    }

    private static void executeCmdi(final Context ctx, final String[] arrayCmd) {
        cmdExamples.insecureCmd(arrayCmd);
        ctx.getResponse().send("text/plain", "OK");
    }

    private static void executeUrl(final Context ctx, String urlString) {
        try {
            URL url;
            try {
                url = new URL(urlString);
            } catch (MalformedURLException e) {
                url = new URL("http://" + urlString);
            }

            URLConnection connection = url.openConnection();
            connection.connect();
            ctx.getResponse().send("text/plain", "OK");
        } catch (Exception e) {
            e.printStackTrace();
            ctx.getResponse().send("text/plain", "http connection failed");
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
