package com.datadoghq.trace.opentelemetry.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import com.datadoghq.trace.opentelemetry.dto.*;
import com.datadoghq.trace.opentracing.controller.OpenTracingController;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.logs.*;
import io.opentelemetry.api.trace.Span;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OpenTelemetryLogsController {
  private final LoggerProvider loggerProvider = GlobalOpenTelemetry.get().getLogsBridge();

  /** Known loggers, populated via createLogger requests. */
  private final Map<String, Logger> loggers = new ConcurrentHashMap<>();

  @PostMapping("/otel/logger/create")
  public void createLogger(@RequestBody CreateLoggerArgs args) {
    LOGGER.info("Creating OTel logger: {}", args);
    String loggerName = args.name();
    if (!loggers.containsKey(loggerName)) {
      loggers.put(
          loggerName,
          loggerProvider
              .loggerBuilder(loggerName)
              .setInstrumentationVersion(args.version())
              .setSchemaUrl(args.schemaUrl())
              .build());
      }
  }

  @PostMapping("/otel/logger/write")
  public void writeLog(@RequestBody WriteLogArgs args) {
    LOGGER.info("Writing OTel log: {}", args);
    String loggerName = args.loggerName();
    Logger logger = loggers.get(loggerName);
    if (logger == null) {
      throw new IllegalStateException(
          "Logger " + loggerName + " not found in registered loggers " + loggers.keySet());
    }
    AutoCloseable scope = null;
    if (args.spanId() != 0) {
      Span span = OpenTelemetryTraceController.getSpan(args.spanId());
      if (span != null) {
        scope = span.makeCurrent();
      } else {
        io.opentracing.Span otSpan = OpenTracingController.getSpan(args.spanId());
        if (otSpan != null) {
          scope = io.opentracing.util.GlobalTracer.get().activateSpan(otSpan);
        } else {
          throw new IllegalStateException("Span not found for span_id: " + args.spanId());
        }
      }
    }
    try {
      Severity severity = Severity.valueOf(args.level().toUpperCase(Locale.ROOT));
      logger.logRecordBuilder()
          .setSeverity(severity)
          .setSeverityText(severity.name())
          .setBody(args.message())
          .emit();
    } finally {
      if (scope != null) {
        try {
          scope.close();
        } catch (Exception ignore) {}
      }
    }
  }

  @PostMapping("/log/otel/flush")
  public FlushResult flushLogs(@RequestBody FlushArgs args) {
    LOGGER.info("Flushing OTel logs: {}", args);
    try {
      // TODO: call internal hook to flush logs
      return new FlushResult(true);
    } catch (Exception e) {
      LOGGER.warn("Failed to flush OTel logs", e);
      return new FlushResult(false);
    }
  }
}
