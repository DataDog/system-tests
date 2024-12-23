package com.datadoghq.trace.opentelemetry.controller;

import static io.opentelemetry.api.trace.SpanKind.CLIENT;
import static io.opentelemetry.api.trace.SpanKind.CONSUMER;
import static io.opentelemetry.api.trace.SpanKind.INTERNAL;
import static io.opentelemetry.api.trace.SpanKind.PRODUCER;
import static io.opentelemetry.api.trace.SpanKind.SERVER;

import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.TraceState;
import java.util.Collection;
import java.util.Iterator;
import java.util.Map;

final class OpenTelemetryTypeHelper {
  private OpenTelemetryTypeHelper() {}

  static SpanKind parseSpanKindNumber(int spanKindNumber) {
    return switch (spanKindNumber) {
      case 0 -> INTERNAL;
      case 1 -> SERVER;
      case 2 -> CLIENT;
      case 3 -> PRODUCER;
      case 4 -> CONSUMER;
      default -> null;
    };
  }

  static Attributes parseAttributes(Map<String, Object> attributes) {
    if (attributes == null || attributes.isEmpty()) {
      return Attributes.empty();
    }
    AttributesBuilder builder = Attributes.builder();
    for (Map.Entry<String, Object> entry : attributes.entrySet()) {
      String key = entry.getKey();
      Object value = entry.getValue();
      // Handle single attribute array value as non array value
      if (value instanceof Collection<?> values && values.size() == 1) {
        value = values.iterator().next();
      }
      if (value instanceof Boolean) {
        builder.put(key, (Boolean) value);
      } else if (value instanceof String) {
        builder.put(key, (String) value);
      } else if (value instanceof Integer) {
        builder.put(key, ((Integer) value));
      } else if (value instanceof Long) {
        builder.put(key, (Long) value);
      } else if (value instanceof Float) {
        builder.put(key, (Float) value);
      } else if (value instanceof Double) {
        builder.put(key, (Double) value);
      } else if (value instanceof Collection<?> values) {
        Object firstValue = values.iterator().next();
        Iterator<?> iterator = values.iterator();
        int count = 0;
        int valueCount = values.size();
        if (firstValue instanceof Boolean) {
          boolean[] parsedValues = new boolean[valueCount];
          while (iterator.hasNext()) {
            parsedValues[count++] = (Boolean) iterator.next();
          }
          builder.put(key, parsedValues);
        } else if (firstValue instanceof String) {
          String[] parsedValues = new String[valueCount];
          while (iterator.hasNext()) {
            parsedValues[count++] = (String) iterator.next();
          }
          builder.put(key, parsedValues);
        } else if (firstValue instanceof Integer) {
          long[] parsedValues = new long[valueCount];
          while (iterator.hasNext()) {
            parsedValues[count++] = (Integer) iterator.next();
          }
          builder.put(key, parsedValues);
        } else if (firstValue instanceof Long) {
          long[] parsedValues = new long[valueCount];
          while (iterator.hasNext()) {
            parsedValues[count++] = (Long) iterator.next();
          }
          builder.put(key, parsedValues);
        } else if (firstValue instanceof Float) {
          double[] parsedValues = new double[valueCount];
          while (iterator.hasNext()) {
            parsedValues[count++] = (Float) iterator.next();
          }
          builder.put(key, parsedValues);
        } else if (firstValue instanceof Double) {
          double[] parsedValues = new double[valueCount];
          while (iterator.hasNext()) {
            parsedValues[count++] = (Double) iterator.next();
          }
          builder.put(key, parsedValues);
        }
      }
    }
    return builder.build();
  }

  static String formatTraceState(TraceState traceState) {
    StringBuilder builder = new StringBuilder();
    traceState.forEach((memberKey, memberValue) -> {
      if (!builder.isEmpty()) {
        builder.append(',');
      }
      builder.append(memberKey).append('=').append(memberValue);
    });
    return builder.toString();
  }
}
