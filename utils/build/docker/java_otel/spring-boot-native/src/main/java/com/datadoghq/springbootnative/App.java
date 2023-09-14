package com.datadoghq.springbootnative;

import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.logs.GlobalLoggerProvider;
import io.opentelemetry.exporter.logging.otlp.OtlpJsonLoggingLogRecordExporter;
import io.opentelemetry.exporter.logging.otlp.OtlpJsonLoggingMetricExporter;
import io.opentelemetry.exporter.logging.otlp.OtlpJsonLoggingSpanExporter;
import io.opentelemetry.exporter.otlp.http.logs.OtlpHttpLogRecordExporter;
import io.opentelemetry.exporter.otlp.http.metrics.OtlpHttpMetricExporter;
import io.opentelemetry.exporter.otlp.http.trace.OtlpHttpSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.logs.LogRecordProcessor;
import io.opentelemetry.sdk.logs.SdkLoggerProvider;
import io.opentelemetry.sdk.logs.export.BatchLogRecordProcessor;
import io.opentelemetry.sdk.logs.export.LogRecordExporter;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.metrics.SdkMeterProviderBuilder;
import io.opentelemetry.sdk.metrics.data.AggregationTemporality;
import io.opentelemetry.sdk.metrics.export.AggregationTemporalitySelector;
import io.opentelemetry.sdk.metrics.export.MetricExporter;
import io.opentelemetry.sdk.metrics.export.PeriodicMetricReader;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.SpanProcessor;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.sdk.trace.export.SpanExporter;
import io.opentelemetry.sdk.trace.samplers.Sampler;
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@ComponentScan(basePackages = {"com.datadoghq.springbootnative"})
public class App {
    public static void main(String[] args) {
        Resource resource = Resource.create(Attributes.of(
                ResourceAttributes.SERVICE_NAME, "otel-system-tests-spring-boot",
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT, "system-tests"));

        OpenTelemetrySdk openTelemetry = OpenTelemetrySdk.builder()
                .setTracerProvider(setupTraceProvider(resource))
                .setMeterProvider(setupMeterProvider(resource))
                .setLoggerProvider(setupLoggerProvider(resource))
                .buildAndRegisterGlobal();
        GlobalLoggerProvider.set(openTelemetry.getSdkLoggerProvider());
        SpringApplication.run(App.class, args);
    }

    private static SdkTracerProvider setupTraceProvider(Resource resource) {
        List<SpanExporter> spanExporters = new ArrayList<>();
        spanExporters.add(OtlpJsonLoggingSpanExporter.create());
        if (isAgentEnabled()) {
            spanExporters.add(
                OtlpHttpSpanExporter.builder()
                    .setEndpoint("http://proxy:8126/v1/traces")
                    .addHeader("dd-protocol", "otlp")
                    .addHeader("dd-otlp-path", "agent")
                    .build());
        }
        if (isIntakeEnabled()) {
            spanExporters.add(
                OtlpHttpSpanExporter.builder()
                    .setEndpoint("http://proxy:8126/api/v0.2/traces")  // send to the proxy first
                    .addHeader("dd-protocol", "otlp")
                    .addHeader("dd-api-key", System.getenv("DD_API_KEY"))
                    .addHeader("dd-otlp-path", "intake")
                    .addHeader("dd-otlp-source", "datadog")
                    .build());
        }
        if (isCollectorEnabled()) {
            spanExporters.add(
                OtlpHttpSpanExporter.builder()
                    .setEndpoint("http://proxy:8126/v1/traces")
                    .addHeader("dd-protocol", "otlp")
                    .addHeader("dd-otlp-path", "collector")
                    .build());
        }

        SpanExporter exporter = SpanExporter.composite(spanExporters);

        SpanProcessor processor = BatchSpanProcessor.builder(exporter)
                .setMaxExportBatchSize(1)
                .build();

        return SdkTracerProvider.builder()
                .addSpanProcessor(processor)
                .setSampler(Sampler.alwaysOn())
                .setResource(resource)
                .build();
    }

    private static SdkMeterProvider setupMeterProvider(Resource resource) {
        List<MetricExporter> metricExporters = new ArrayList<>();
        metricExporters.add(OtlpJsonLoggingMetricExporter.create(AggregationTemporality.DELTA));
        if (isAgentEnabled()) {
            metricExporters.add(
                    OtlpHttpMetricExporter.builder()
                            .setEndpoint("http://proxy:8126/v1/metrics")
                            .addHeader("dd-protocol", "otlp")
                            .addHeader("dd-otlp-path", "agent")
                            .setAggregationTemporalitySelector(AggregationTemporalitySelector.deltaPreferred())
                            .build());
        }
        if (isCollectorEnabled()) {
            metricExporters.add(
                    OtlpHttpMetricExporter.builder()
                            .setEndpoint("http://proxy:8126/v1/metrics")
                            .addHeader("dd-protocol", "otlp")
                            .addHeader("dd-otlp-path", "collector")
                            .setAggregationTemporalitySelector(AggregationTemporalitySelector.deltaPreferred())
                            .build());
        }
        SdkMeterProviderBuilder builder = SdkMeterProvider.builder().setResource(resource);
        for (MetricExporter exporter : metricExporters) {
            builder.registerMetricReader(
                    PeriodicMetricReader.builder(exporter).setInterval(1L, TimeUnit.MILLISECONDS).build());
        }
        return builder.build();
    }

    private static SdkLoggerProvider setupLoggerProvider(Resource resource) {
        List<LogRecordExporter> logRecordExporters = new ArrayList<>();
        logRecordExporters.add(OtlpJsonLoggingLogRecordExporter.create());
        if (isAgentEnabled()) {
            logRecordExporters.add(
                    OtlpHttpLogRecordExporter.builder()
                            .setEndpoint("http://proxy:8126/v1/logs")
                            .addHeader("dd-protocol", "otlp")
                            .addHeader("dd-otlp-path", "agent")
                            .build());
        }
        if (isCollectorEnabled()) {
            logRecordExporters.add(
                    OtlpHttpLogRecordExporter.builder()
                            .setEndpoint("http://proxy:8126/v1/logs")
                            .addHeader("dd-protocol", "otlp")
                            .addHeader("dd-otlp-path", "collector")
                            .build());
        }
        LogRecordExporter exporter = LogRecordExporter.composite(logRecordExporters);
        LogRecordProcessor processor = BatchLogRecordProcessor.builder(exporter)
                .setMaxExportBatchSize(1)
                .setMaxQueueSize(1)
                .build();
        return SdkLoggerProvider.builder()
                .addLogRecordProcessor(processor)
                .setResource(resource)
                .build();
    }

    private static boolean isAgentEnabled() {
        return "true".equalsIgnoreCase(System.getenv("OTEL_SYSTEST_INCLUDE_AGENT"));
    }

    private static boolean isCollectorEnabled() {
        return "true".equalsIgnoreCase(System.getenv("OTEL_SYSTEST_INCLUDE_COLLECTOR"));
    }

    private static boolean isIntakeEnabled() {
        return "true".equalsIgnoreCase(System.getenv("OTEL_SYSTEST_INCLUDE_INTAKE"));
    }
}
