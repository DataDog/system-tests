package com.datadoghq.opentracing.dto;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public record KeyValue(String key, String value) {

  public static class KeyValueListDeserializer extends JsonDeserializer<List<KeyValue>> {
    @Override
    public List<KeyValue> deserialize(JsonParser jsonParser, DeserializationContext deserializationContext) throws IOException {
      JsonNode arrayNode = jsonParser.getCodec().readTree(jsonParser);
      List<KeyValue> list = new ArrayList<>();
      for (JsonNode elementNode : arrayNode) {
        String key = elementNode.get(0).asText();
        String value = elementNode.get(1).asText();
        list.add(new KeyValue(key, value));
      }
      return list;
    }
  }

  public static class KeyValueListSerializer extends JsonSerializer<List<KeyValue>> {
    @Override
    public void serialize(List<KeyValue> keyValues, JsonGenerator jsonGenerator, SerializerProvider serializerProvider) throws IOException {
      jsonGenerator.writeStartArray();
      for (KeyValue keyValue : keyValues) {
        jsonGenerator.writeStartArray();
        jsonGenerator.writeString(keyValue.key());
        jsonGenerator.writeString(keyValue.value());
        jsonGenerator.writeEndArray();
      }
      jsonGenerator.writeEndArray();
    }
  }
}
