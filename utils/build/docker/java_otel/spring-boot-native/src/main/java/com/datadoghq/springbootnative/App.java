package com.datadoghq.springbootnative;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.propagation.ContextPropagators;
import io.opentelemetry.context.propagation.TextMapPropagator;
import io.opentelemetry.exporter.logging.otlp.OtlpJsonLoggingSpanExporter;
import io.opentelemetry.exporter.otlp.http.trace.OtlpHttpSpanExporter;
import io.opentelemetry.extension.trace.propagation.B3Propagator;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.SpanProcessor;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.sdk.trace.export.SpanExporter;
import io.opentelemetry.sdk.trace.samplers.Sampler;
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;
import java.util.logging.Logger;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@ComponentScan(basePackages = {"com.datadoghq.springbootnative"})
public class App {
    private static final Logger logger = Logger.getLogger(App.class.getName());

    public static void main(String[] args) {
        Resource resource = Resource.create(Attributes.of(
                ResourceAttributes.SERVICE_NAME, "otel-system-tests-spring-boot",
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT, "system-tests"));

        OtlpHttpSpanExporter intakeExporter = OtlpHttpSpanExporter.builder()
                .setEndpoint("http://runner:8126/api/v0.2/traces")
                .addHeader("dd-protocol", "otlp")
                .addHeader("dd-api-key", System.getenv("DD_API_KEY"))
                .build();

        SpanExporter loggingSpanExporter = OtlpJsonLoggingSpanExporter.create();

        SpanExporter exporter = SpanExporter.composite(intakeExporter, loggingSpanExporter);

        SpanProcessor processor = BatchSpanProcessor.builder(exporter)
                .setMaxExportBatchSize(1)
                .build();

        SdkTracerProvider sdkTracerProvider = SdkTracerProvider.builder()
                .addSpanProcessor(processor)
                .setSampler(Sampler.alwaysOn())
                .setResource(resource)
                .build();

        String propagator = System.getenv().getOrDefault("OTEL_PROPAGATORS", "tracecontext");
        TextMapPropagator textPropagator = switch (propagator) {
            case "tracecontext" -> W3CTraceContextPropagator.getInstance();
            case "b3" -> B3Propagator.injectingSingleHeader();
            case "b3multi" -> B3Propagator.injectingMultiHeaders();
            default -> TextMapPropagator.noop();
        };
        OpenTelemetry openTelemetry = OpenTelemetrySdk.builder()
                .setTracerProvider(sdkTracerProvider)
                .setPropagators(ContextPropagators.create(textPropagator))
                .buildAndRegisterGlobal();

        logger.info("Using OpenTelemetry Propagator: " + openTelemetry.getPropagators().getTextMapPropagator());

        SpringApplication.run(App.class, args);
    }
}
