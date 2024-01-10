package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static datadog.trace.api.DDTags.RESOURCE_NAME;
import static datadog.trace.api.DDTags.SERVICE_NAME;
import static datadog.trace.api.DDTags.SPAN_TYPE;
import static java.util.concurrent.TimeUnit.MICROSECONDS;

import com.datadoghq.client.APMClientGrpc;
import com.datadoghq.client.ApmTestClient;
import com.datadoghq.client.ApmTestClient.DistributedHTTPHeaders;
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
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTraceId;
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
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapGetter;

import javax.annotation.Nullable;
import javax.annotation.ParametersAreNonnullByDefault;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

public class OpenTelemetryClient extends APMClientGrpc.APMClientImplBase {
    private final Tracer tracer;
    private final Map<Long, Span> spans;

    OpenTelemetryClient() {
        this.tracer = GlobalOpenTelemetry.getTracer("java-client");
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
            if (request.hasHttpHeaders() && request.getHttpHeaders().getHttpHeadersCount() > 0) {
                // Won't work as the extracted content will contain a current span without wrapped DDSpan delegate
                // Limitation from the current tracer OTel instrumentation implementation
                Context extractedContext = W3CTraceContextPropagator.getInstance().extract(
                        Context.current(),
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
