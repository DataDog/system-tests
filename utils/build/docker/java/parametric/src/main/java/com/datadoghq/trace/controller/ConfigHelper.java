package com.datadoghq.trace.controller;

import static java.util.stream.Collectors.joining;

import java.lang.reflect.Method;
import java.util.Collection;
import java.util.Map;

final class ConfigHelper {
  private static final String GET_METHOD_NAME = "get";
  private static final String CONFIG_CLASS_NAME = "datadog.trace.api.Config";
  private static final String INSTRUMENTER_CONFIG_CLASS_NAME = "datadog.trace.api.InstrumenterConfig";
  private final Class<?> configClass;
  private final Object config;
  private final Class<?> instrumenterClass;
  private final Object instrumenterConfig;

  public ConfigHelper() {
    try {
      this.configClass = Class.forName(CONFIG_CLASS_NAME);
      this.config = getStaticInstanceOf(this.configClass);
      this.instrumenterClass = Class.forName(INSTRUMENTER_CONFIG_CLASS_NAME);
      this.instrumenterConfig = getStaticInstanceOf(this.instrumenterClass);
    } catch (ReflectiveOperationException e) {
      throw new IllegalStateException("Failed to initialize config helper", e);
    }
  }

  public String getConfigValue(String accessorName) {
    Object value = getValue(this.configClass, this.config, accessorName);
    return value == null ? null : value.toString();
  }

  public String getConfigCollectionValues(String accessorName, String delimiter) {
    Object value = getValue(this.configClass, this.config, accessorName);
    if (value instanceof Collection<?> collection) {
      return collection.stream()
          .map(Object::toString)
          .collect(joining(delimiter));
    } else {
      return value == null ? null : value.toString();
    }
  }

  public String getConfigMapValues(String accessorName, String delimiter, String pair) {
    Object value = getValue(this.configClass, this.config, accessorName);
    if (value instanceof Map<?, ?> map) {
      StringBuilder builder = new StringBuilder();
      map.forEach((k, v) ->
          builder.append(k).append(pair).append(v).append(delimiter));
      if (!builder.isEmpty()) {
        builder.setLength(builder.length() - delimiter.length());
      }
      return builder.toString();
    } else {
      return value == null ? null : value.toString();
    }
  }

  public String getInstrumenterConfigValue(String accessorName) {
    Object value = getValue(this.instrumenterClass, this.instrumenterConfig, accessorName);
    return value == null ? null : value.toString();
  }

  private Object getValue(Class<?> configClass, Object config, String accessorName) {
    try {
      Method method = configClass.getMethod(accessorName);
      return method.invoke(config);
    } catch (ReflectiveOperationException e) {
      throw new IllegalStateException(
          "Failed get config value from " + configClass + "." + accessorName + "()", e);
    }
  }

  private static Object getStaticInstanceOf(Class<?> clazz) throws ReflectiveOperationException{
    Method getConfigMethod = clazz.getMethod(GET_METHOD_NAME);
    return getConfigMethod.invoke(null);
  }
}
