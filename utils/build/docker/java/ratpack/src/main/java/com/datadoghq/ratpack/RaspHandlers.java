package com.datadoghq.ratpack;


import static com.datadoghq.ratpack.Main.DATA_SOURCE;
import static ratpack.jackson.Jackson.fromJson;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
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

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

public class RaspHandlers {

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
}
