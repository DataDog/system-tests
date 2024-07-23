package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static datadog.trace.api.DDTags.RESOURCE_NAME;
import static datadog.trace.api.DDTags.SERVICE_NAME;
import static datadog.trace.api.DDTags.SPAN_TYPE;
import static java.util.concurrent.TimeUnit.MICROSECONDS;

import com.datadoghq.client.APMClientGrpc;
import com.datadoghq.client.ApmTestClient;
import com.datadoghq.client.ApmTestClient.DistributedHTTPHeaders;
import com.datadoghq.client.ApmTestClient.GetTraceConfigArgs;
import com.datadoghq.client.ApmTestClient.GetTraceConfigReturn;
import com.datadoghq.client.ApmTestClient.ListVal;
import com.datadoghq.client.ApmTestClient.OtelEndSpanArgs;
import com.datadoghq.client.ApmTestClient.OtelEndSpanReturn;
import com.datadoghq.client.ApmTestClient.OtelIsRecordingArgs;
import com.datadoghq.client.ApmTestClient.OtelIsRecordingReturn;
import com.datadoghq.client.ApmTestClient.OtelSetAttributesArgs;
import com.datadoghq.client.ApmTestClient.OtelSetAttributesReturn;
import com.datadoghq.client.ApmTestClient.OtelSetNameArgs;
import com.datadoghq.client.ApmTestClient.OtelSetNameReturn;
import com.datadoghq.client.ApmTestClient.OtelSetStatusArgs;
import com.datadoghq.client.ApmTestClient.OtelSetStatusReturn;
import com.datadoghq.client.ApmTestClient.OtelSpanContextArgs;
import com.datadoghq.client.ApmTestClient.OtelSpanContextReturn;
import com.datadoghq.client.ApmTestClient.OtelStartSpanArgs;
import com.datadoghq.client.ApmTestClient.OtelStartSpanReturn;
import com.datadoghq.client.ApmTestClient.SpanLink;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.TracePropagationStyle;
import io.grpc.stub.StreamObserver;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapPropagator;
import java.lang.reflect.Method;
import javax.annotation.Nullable;
import javax.annotation.ParametersAreNonnullByDefault;
import java.util.HashMap;
import java.util.Set;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

public class OpenTelemetryClient extends APMClientGrpc.APMClientImplBase {
    private final Tracer tracer;
    private final TextMapPropagator propagator;
    private final Map<Long, Span> spans;

    OpenTelemetryClient() {
        this.tracer = GlobalOpenTelemetry.getTracer("java-client");
        this.propagator = GlobalOpenTelemetry.getPropagators().getTextMapPropagator();
        this.spans = new HashMap<>();
    }

    private static Attributes parseAttributes(ApmTestClient.Attributes attributes) {
        AttributesBuilder builder = Attributes.builder();
        for (Map.Entry<String, ListVal> entry : attributes.getKeyValsMap().entrySet()) {
            String key = entry.getKey();
            ListVal values = entry.getValue();
            int valueCount = values.getValCount();
            if (valueCount < 1) {
                continue;
            }
            ApmTestClient.AttrVal firstValue = values.getVal(0);
            ApmTestClient.AttrVal.ValCase entryValueType = firstValue.getValCase();
            if (valueCount == 1) {
                switch (entryValueType) {
                    case BOOL_VAL:
                        builder.put(key, firstValue.getBoolVal());
                        break;
                    case STRING_VAL:
                        builder.put(key, firstValue.getStringVal());
                        break;
                    case DOUBLE_VAL:
                        builder.put(key, firstValue.getDoubleVal());
                        break;
                    case INTEGER_VAL:
                        builder.put(key, firstValue.getIntegerVal());
                        break;
                    default:
                }
            } else {
                switch (entryValueType) {
                    case BOOL_VAL: {
                        boolean[] parsedValues = new boolean[valueCount];
                        for (int i = 0; i < valueCount; i++) {
                            parsedValues[i] = values.getVal(i).getBoolVal();
                        }
                        builder.put(key, parsedValues);
                        break;
                    }
                    case STRING_VAL: {
                        String[] parsedValues = values.getValList()
                                .stream()
                                .map(ApmTestClient.AttrVal::getStringVal)
                                .toArray(String[]::new);
                        builder.put(key, parsedValues);
                        break;
                    }
                    case DOUBLE_VAL: {
                        double[] parsedValues = values.getValList()
                                .stream()
                                .mapToDouble(ApmTestClient.AttrVal::getDoubleVal)
                                .toArray();
                        builder.put(key, parsedValues);
                        break;
                    }
                    case INTEGER_VAL: {
                        long[] parsedValues = values.getValList()
                                .stream()
                                .mapToLong(ApmTestClient.AttrVal::getIntegerVal)
                                .toArray();
                        builder.put(key, parsedValues);
                        break;
                    }
                    default:
                }
            }
        }
        return builder.build();
    }

    private static SpanKind parseSpanKindNumber(long spanKindNumber) {
        switch ((int) spanKindNumber) {
            case 1:
                return SpanKind.INTERNAL;
            case 2:
                return SpanKind.SERVER;
            case 3:
                return SpanKind.CLIENT;
            case 4:
                return SpanKind.PRODUCER;
            case 5:
                return SpanKind.CONSUMER;
            case 0:
            default:
                return null;
        }
    }

    @Override
    public void getTraceConfig(GetTraceConfigArgs request, StreamObserver<GetTraceConfigReturn> responseObserver) {
        LOGGER.info("Getting tracer config");
        try
        {
            // Use reflection to get the static Config instance
            Class configClass = Class.forName("datadog.trace.api.Config");
            Method getConfigMethod = configClass.getMethod("get");

            Class instrumenterConfigClass = Class.forName("datadog.trace.api.InstrumenterConfig");
            Method getInstrumenterConfigMethod = instrumenterConfigClass.getMethod("get");

            Object configObject = getConfigMethod.invoke(null);
            Object instrumenterConfigObject = getInstrumenterConfigMethod.invoke(null);

            Method getServiceName = configClass.getMethod("getServiceName");
            Method getEnv = configClass.getMethod("getEnv");
            Method getVersion = configClass.getMethod("getVersion");
            Method getTraceSampleRate = configClass.getMethod("getTraceSampleRate");
            Method isTraceEnabled = configClass.getMethod("isTraceEnabled");
            Method isRuntimeMetricsEnabled = configClass.getMethod("isRuntimeMetricsEnabled");
            Method getGlobalTags = configClass.getMethod("getGlobalTags");
            Method getTracePropagationStylesToInject = configClass.getMethod("getTracePropagationStylesToInject");
            Method isDebugEnabled = configClass.getMethod("isDebugEnabled");
            Method getLogLevel = configClass.getMethod("getLogLevel");

            Method isTraceOtelEnabled = instrumenterConfigClass.getMethod("isTraceOtelEnabled");

            Map<String, String> configMap = new HashMap<>();
            configMap.put("dd_service", getServiceName.invoke(configObject).toString());
            configMap.put("dd_env", getEnv.invoke(configObject).toString());
            configMap.put("dd_version", getVersion.invoke(configObject).toString());
            configMap.put("dd_log_level", Optional.ofNullable(getLogLevel.invoke(configObject)).map(Object::toString).orElse(null));
            configMap.put("dd_trace_enabled", isTraceEnabled.invoke(configObject).toString());
            configMap.put("dd_runtime_metrics_enabled", isRuntimeMetricsEnabled.invoke(configObject).toString());
            configMap.put("dd_trace_debug", isDebugEnabled.invoke(configObject).toString());
            configMap.put("dd_trace_otel_enabled", isTraceOtelEnabled.invoke(instrumenterConfigObject).toString());
            // configMap.put("dd_trace_sample_ignore_parent", Config.get());

            Object sampleRate = getTraceSampleRate.invoke(configObject);
            if (sampleRate instanceof Double) {
                configMap.put("dd_trace_sample_rate", String.valueOf((Double)sampleRate));
            }

            Object globalTags = getGlobalTags.invoke(configObject);
            if (globalTags != null) {
                String result = ((Map<String, String>)globalTags).entrySet()
                    .stream()
                    .map(entry -> entry.getKey() + ":" + entry.getValue())
                    .collect(Collectors.joining(","));

                configMap.put("dd_tags", result);
            }

            Object propagationStyles = getTracePropagationStylesToInject.invoke(configObject);
            if (propagationStyles != null) {
                String result = ((Set<TracePropagationStyle>)propagationStyles)
                    .stream()
                    .map(style -> style.toString())
                    .collect(Collectors.joining(","));

                configMap.put("dd_trace_propagation_style", result);
            }

            configMap.values().removeIf(Objects::isNull);
            responseObserver.onNext(GetTraceConfigReturn.newBuilder()
                    .putAllConfig(configMap)
                    .build());
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelStartSpan(OtelStartSpanArgs request, StreamObserver<OtelStartSpanReturn> responseObserver) {
        LOGGER.info("Starting OTel span: {}", request);
        try {
            // Build span from request
            SpanBuilder builder = this.tracer.spanBuilder(request.getName());
            long parentId = request.hasParentId() ? request.getParentId() : 0L;
            if (parentId != 0L) {
                Span parentSpan = getSpan(parentId, responseObserver);
                if (parentSpan == null) {
                    return;
                }
                Context contextWithParentSpan = parentSpan.storeInContext(Context.root());
                builder.setParent(contextWithParentSpan);
            }
            if (request.hasSpanKind()) {
                SpanKind spanKind = parseSpanKindNumber(request.getSpanKind());
                if (spanKind != null) {
                    builder.setSpanKind(spanKind);
                }
            }
            if (request.hasTimestamp()) {
                builder.setStartTimestamp(request.getTimestamp(), MICROSECONDS);
            }
            if (request.getSpanLinksCount() > 0) {
                for (SpanLink spanLink : request.getSpanLinksList()) {
                    SpanContext spanContext = null;
                    LOGGER.warn("Span link: "+spanLink);
                    if (spanLink.hasParentId()) {
                        LOGGER.warn("Parent id found");
                        Span span = getSpan(spanLink.getParentId(), responseObserver);
                        if (span == null) {
                            return;
                        }
                        LOGGER.warn("Parent span found");
                        spanContext = span.getSpanContext();
                    } else if (spanLink.hasHttpHeaders()) {
                        Context extractedContext = this.propagator.extract(
                            Context.root(),
                            spanLink.getHttpHeaders(),
                            HeadersTextMapGetter.INSTANCE
                        );
                        spanContext = Span.fromContext(extractedContext).getSpanContext();
                        LOGGER.warn("Extracted context {} | valid {}", spanContext, spanContext.isValid());
                    }
                    if (spanContext != null && spanContext.isValid()) {
                        if (spanLink.hasAttributes()) {
                            LOGGER.warn("Adding links with attributes {}", spanContext);
                            builder.addLink(spanContext, parseAttributes(spanLink.getAttributes()));
                        } else {
                            LOGGER.warn("Adding link without attributes {}", spanContext);
                            builder.addLink(spanContext);
                        }
                    }
                }
            }
            if (request.hasHttpHeaders() && request.getHttpHeaders().getHttpHeadersCount() > 0) {
                Context extractedContext = this.propagator.extract(
                        Context.root(),
                        request.getHttpHeaders(),
                        HeadersTextMapGetter.INSTANCE
                );
                builder.setParent(extractedContext);
            }
            if (request.hasAttributes()) {
                builder.setAllAttributes(parseAttributes(request.getAttributes()));
            }
            if (request.hasResource()) {
                builder.setAttribute(RESOURCE_NAME, request.getResource());
            }
            if (request.hasService()) {
                builder.setAttribute(SERVICE_NAME, request.getService());
            }
            if (request.hasType()) {
                builder.setAttribute(SPAN_TYPE, request.getType());
            }
            Span span = builder.startSpan();
            // Store span
            long spanId = DDSpanId.fromHex(span.getSpanContext().getSpanId());
            long traceId = DDTraceId.fromHex(span.getSpanContext().getTraceId()).toLong();
            this.spans.put(spanId, span);
            // Complete request
            responseObserver.onNext(OtelStartSpanReturn.newBuilder()
                    .setSpanId(spanId)
                    .setTraceId(traceId)
                    .build());
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelEndSpan(OtelEndSpanArgs request, StreamObserver<OtelEndSpanReturn> responseObserver) {
        LOGGER.info("Ending OTel span: {}", request);
        try {
            Span span = getSpan(request.getId(), responseObserver);
            if (span != null) {
                if (request.hasTimestamp()) {
                    span.end(request.getTimestamp(), MICROSECONDS);
                } else {
                    span.end();
                }
                responseObserver.onNext(OtelEndSpanReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelIsRecording(OtelIsRecordingArgs request, StreamObserver<OtelIsRecordingReturn> responseObserver) {
        LOGGER.info("Checking OTel span recording: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                responseObserver.onNext(OtelIsRecordingReturn.newBuilder().setIsRecording(span.isRecording()).build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelSpanContext(OtelSpanContextArgs request, StreamObserver<OtelSpanContextReturn> responseObserver) {
        LOGGER.info("Getting OTel span context: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                SpanContext spanContext = span.getSpanContext();

                responseObserver.onNext(OtelSpanContextReturn.newBuilder()
                        .setSpanId(spanContext.getSpanId())
                        .setTraceId(spanContext.getTraceId())
                        .setTraceFlags(spanContext.getTraceFlags().asHex()) // TODO Check hex string mapping?
//                                .setTraceState(spanContext.getTraceState()) // TODO String mapping?
                        .setRemote(spanContext.isRemote())
                        .build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelSetStatus(OtelSetStatusArgs request, StreamObserver<OtelSetStatusReturn> responseObserver) {
        LOGGER.info("Setting OTel span status: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                span.setStatus(StatusCode.valueOf(request.getCode()), request.getDescription());
                responseObserver.onNext(OtelSetStatusReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelSetName(OtelSetNameArgs request, StreamObserver<OtelSetNameReturn> responseObserver) {
        LOGGER.info("Setting OTel span name: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                span.updateName(request.getName());
                responseObserver.onNext(OtelSetNameReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelSetAttributes(OtelSetAttributesArgs request, StreamObserver<OtelSetAttributesReturn> responseObserver) {
        LOGGER.info("Setting OTel span attributes: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                span.setAllAttributes(parseAttributes(request.getAttributes()));
                responseObserver.onNext(OtelSetAttributesReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    private Span getSpan(long spanId, StreamObserver<?> responseObserver) {
        Span span = this.spans.get(spanId);
        if (span == null) {
            String message = "OTel span " + spanId + " does not exist.";
            LOGGER.warn(message);
            responseObserver.onError(new IllegalArgumentException(message));
            return null;
        }
        return span;
    }

    void clearSpans() {
        this.spans.clear();
    }

    @ParametersAreNonnullByDefault
    private static class HeadersTextMapGetter implements TextMapGetter<DistributedHTTPHeaders> {
        private static final HeadersTextMapGetter INSTANCE = new HeadersTextMapGetter();

        @Override
        public Iterable<String> keys(DistributedHTTPHeaders headers) {
            return headers.getHttpHeadersList()
                    .stream()
                    .map(ApmTestClient.HeaderTuple::getKey)
                    .collect(Collectors.toList());
        }

        @Nullable
        @Override
        public String get(@Nullable DistributedHTTPHeaders headers, String key) {
            if (headers == null) {
                return null;
            }
            return headers.getHttpHeadersList()
                    .stream()
                    .filter(t -> t.getKey().equals(key))
                    .findAny()
                    .map(ApmTestClient.HeaderTuple::getValue)
                    .orElse(null);
        }
    }
}
