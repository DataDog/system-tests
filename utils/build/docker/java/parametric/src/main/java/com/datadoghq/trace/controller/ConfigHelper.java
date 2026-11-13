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

  public String getEffectiveLogLevel() {
    try {
      // The agent shades SLF4J; the application's own LoggerFactory has a separate configuration.
      // Only use the public SLF4J interface, not implementation fields or raw environment values.
      Class<?> loggerFactory = Class.forName("datadog.slf4j.LoggerFactory");
      Class<?> loggerInterface = Class.forName("datadog.slf4j.Logger");
      Object logger = loggerFactory.getMethod("getLogger", String.class)
          .invoke(null, "datadog.trace.parametric.log-level");
      for (String level : new String[] {"Trace", "Debug", "Info", "Warn", "Error"}) {
        if ((Boolean) loggerInterface.getMethod("is" + level + "Enabled").invoke(logger)) {
          return level.toLowerCase(java.util.Locale.ROOT);
        }
      }
      return "off";
    } catch (ClassNotFoundException e) {
      // Keep the existing config endpoint usable with older agent logging packages.
      return null;
    } catch (ReflectiveOperationException e) {
      throw new IllegalStateException("Failed to read effective tracer log level", e);
    }
  }

  public String getConfigValue(String accessorName) {
    Object value = getValue(this.configClass, this.config, accessorName);
    return value == null ? null : value.toString();
  }

  /** Access a public configuration getter that may not exist in older tracer releases. */
  public String getOptionalConfigValue(String accessorName) {
    try {
      Method method = this.configClass.getMethod(accessorName);
      Object value = method.invoke(this.config);
      return value == null ? null : value.toString();
    } catch (NoSuchMethodException e) {
      return null;
    } catch (ReflectiveOperationException e) {
      throw new IllegalStateException(
          "Failed get config value from " + this.configClass + "." + accessorName + "()", e);
    }
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
