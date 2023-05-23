package com.datadoghq.springbootnative;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.exporter.logging.otlp.OtlpJsonLoggingSpanExporter;
import io.opentelemetry.exporter.otlp.http.trace.OtlpHttpSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.SpanProcessor;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.sdk.trace.export.SpanExporter;
import io.opentelemetry.sdk.trace.samplers.Sampler;
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;
import java.util.ArrayList;
import java.util.List;
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

        OpenTelemetry openTelemetry = OpenTelemetrySdk.builder()
                .setTracerProvider(setupTraceProvider(resource))
                .buildAndRegisterGlobal();

        SpringApplication.run(App.class, args);
    }

    private static SdkTracerProvider setupTraceProvider(Resource resource) {
        List<SpanExporter> spanExporters = new ArrayList<>();
        spanExporters.add(OtlpJsonLoggingSpanExporter.create());
        if ("true".equalsIgnoreCase(System.getenv("OTEL_SYSTEST_INCLUDE_AGENT"))) {
            spanExporters.add(
                OtlpHttpSpanExporter.builder()
                    .setEndpoint("http://proxy:8126/v1/traces")
                    .addHeader("dd-protocol", "otlp")
                    .addHeader("dd-otlp-path", "agent")
                    .build());
        }
        if ("true".equalsIgnoreCase(System.getenv("OTEL_SYSTEST_INCLUDE_INTAKE"))) {
            spanExporters.add(
                OtlpHttpSpanExporter.builder()
                    .setEndpoint("http://proxy:8126/api/v0.2/traces")  // send to the proxy first
                    .addHeader("dd-protocol", "otlp")
                    .addHeader("dd-api-key", System.getenv("DD_API_KEY"))
                    .addHeader("dd-otlp-path", "intake")
                    .addHeader("dd-otlp-source", "datadog")
                    .build());
        }
        if ("true".equalsIgnoreCase(System.getenv("OTEL_SYSTEST_INCLUDE_COLLECTOR"))) {
            spanExporters.add(
                OtlpHttpSpanExporter.builder()
                    .setEndpoint("http://proxy:8126/v1/traces")
                    .addHeader("dd-protocol", "otlp")
                    .addHeader("dd-otlp-path", "collector")
                    .build());
        }

        SpanExporter exporter = SpanExporter.composite(spanExporters.toArray(new SpanExporter[]{}));

        SpanProcessor processor = BatchSpanProcessor.builder(exporter)
                .setMaxExportBatchSize(1)
                .build();

        return SdkTracerProvider.builder()
                .addSpanProcessor(processor)
                .setSampler(Sampler.alwaysOn())
                .setResource(resource)
                .build();
    }
}
