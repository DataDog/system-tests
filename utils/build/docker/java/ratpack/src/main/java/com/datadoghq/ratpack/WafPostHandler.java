package com.datadoghq.ratpack;

import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.google.common.reflect.TypeToken;
import ratpack.exec.Promise;
import ratpack.form.Form;
import ratpack.handling.Context;
import ratpack.handling.Handler;
import ratpack.http.MediaType;
import ratpack.http.TypedData;
import ratpack.parse.Parse;
import ratpack.parse.ParserSupport;
import ratpack.registry.Registry;

import static ratpack.jackson.Jackson.fromJson;

public class WafPostHandler implements Handler {

    @Override
    public void handle(Context ctx) throws Exception {
        MediaType contentType = ctx.getRequest().getContentType();
        if (contentType.isForm()) {
            ctx.insert(FormHandler.INSTANCE);
        } else if (contentType.isJson()) {
            ctx.insert(JsonHandler.INSTANCE);
        } else if (contentType.getType().equals("application/xml") || contentType.getType().equals("text/xml")) {
            ctx.insert(Registry.single(XmlParser.INSTANCE), XmlHandler.INSTANCE);
        } else {
            // We can get arbitrary content-types from tests and still a expect 200 response, not 404.
            ctx.getResponse().send("ok");
        }
    }


    public static Promise<?> consumeParsedBody(final Context ctx) {
        final MediaType contentType = ctx.getRequest().getContentType();
        if (contentType.isEmpty()) {
            return ctx.getRequest().getBody().map(TypedData::getText);
        }
        if (contentType.isForm()) {
            return ctx.parse(Form.class);
        } else if (contentType.isJson()) {
            return ctx.parse(fromJson(Object.class));
        }
        return ctx.getRequest().getBody().map(TypedData::getText);
    }

     enum FormHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var form = ctx.parse(Form.class);
            form.then(f -> {
                ctx.getResponse().send("text/plain", f.getAll().toString());
            });
        }
    }

    enum JsonHandler implements Handler {
        INSTANCE;

        @Override
        public void handle(Context ctx) throws Exception {
            var obj = ctx.parse(fromJson(Object.class));
            obj.then((Object o) -> ctx.getResponse().send("text/plain", o.toString()));
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
            var xml = ctx.parse(Parse.of(XmlObject.class));
            xml.then(x -> ctx.getResponse().send("text/plain", x.toString()));
        }
    }


    @JacksonXmlRootElement
    public static class XmlObject {
        @JacksonXmlText
        public String value;

        @JacksonXmlProperty(isAttribute = true)
        public String attack;

        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder("AElement{");
            sb.append("value='").append(value).append('\'');
            sb.append(", attack='").append(attack).append('\'');
            sb.append('}');
            return sb.toString();
        }
    }
}
