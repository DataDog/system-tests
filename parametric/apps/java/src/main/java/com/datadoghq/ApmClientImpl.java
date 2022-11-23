package com.datadoghq;

import static com.datadoghq.App.LOGGER;

import com.datadoghq.client.APMClientGrpc;
import com.datadoghq.client.ApmTestClient;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTags;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.internal.InternalTracer;
import io.grpc.stub.StreamObserver;
import io.opentracing.Span;
import io.opentracing.Tracer;
import io.opentracing.tag.Tags;

import java.util.HashMap;
import java.util.Map;

public class ApmClientImpl extends APMClientGrpc.APMClientImplBase {
    private final Tracer tracer;
    private final Map<Long, Span> spans;

    public ApmClientImpl(Tracer tracer) {
        this.tracer = tracer;
        this.spans = new HashMap<>();
    }

    @Override
    public void startSpan(ApmTestClient.StartSpanArgs request, StreamObserver<ApmTestClient.StartSpanReturn> responseObserver) {
        LOGGER.info("Creating span: " + request.toString());
        Tracer.SpanBuilder builder = this.tracer.buildSpan(request.getName());
        if (request.hasService()) {
            builder.withTag(DDTags.SERVICE_NAME, request.getService());
        }
        if (request.hasParentId() && request.getParentId() > 0) {
            Span parentSpan = getSpan(request.getParentId(), responseObserver);
            if (parentSpan == null) {
                return;
            }
            builder.asChildOf(parentSpan);
        }
        if (request.hasResource()) {
            builder.withTag(DDTags.RESOURCE_NAME, request.getResource());
        }
        if (request.hasType()) {
            builder.withTag(DDTags.SPAN_TYPE, request.getType());
        }
        if (request.hasOrigin()) {
            builder.withTag(DDTags.ORIGIN_KEY, request.getOrigin());
        }

        Span span = builder.start();
        long spanId = DDSpanId.from(span.context().toSpanId());
        long traceId = DDTraceId.from(span.context().toTraceId()).toLong();
        this.spans.put(spanId, span);

        responseObserver.onNext(ApmTestClient.StartSpanReturn.newBuilder()
                .setSpanId(spanId)
                .setTraceId(traceId)
                .build()
        );
        responseObserver.onCompleted();
    }

    @Override
    public void finishSpan(ApmTestClient.FinishSpanArgs request, StreamObserver<ApmTestClient.FinishSpanReturn> responseObserver) {
        LOGGER.info("Finishing span: " + request.toString());
        Span span = getSpan(request.getId(), responseObserver);
        if (span != null) {
            span.finish();
            responseObserver.onNext(ApmTestClient.FinishSpanReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void spanSetMeta(ApmTestClient.SpanSetMetaArgs request, StreamObserver<ApmTestClient.SpanSetMetaReturn> responseObserver) {
        LOGGER.info("Setting meta span: " + request.toString());
        Span span = getSpan(request.getSpanId(), responseObserver);
        if (span != null) {
            span.setTag(request.getKey(), request.getValue());
            responseObserver.onNext(ApmTestClient.SpanSetMetaReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void spanSetMetric(ApmTestClient.SpanSetMetricArgs request, StreamObserver<ApmTestClient.SpanSetMetricReturn> responseObserver) {
        LOGGER.info("Setting span metric: " + request.toString());
        Span span = getSpan(request.getSpanId(), responseObserver);
        if (span != null) {
            span.setTag(request.getKey(), request.getValue());
            responseObserver.onNext(ApmTestClient.SpanSetMetricReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void spanSetError(ApmTestClient.SpanSetErrorArgs request, StreamObserver<ApmTestClient.SpanSetErrorReturn> responseObserver) {
        LOGGER.info("Setting span error: " + request.toString());
        Span span = getSpan(request.getSpanId(), responseObserver);
        if (span != null) {
            span.setTag(Tags.ERROR, true);
            if (request.hasType()) {
                span.setTag(DDTags.ERROR_TYPE, request.getType());
            }
            if (request.hasMessage()) {
                span.setTag(DDTags.ERROR_MSG, request.getMessage());
            }
            if (request.hasMessage()) {
                span.setTag(DDTags.ERROR_STACK, request.getStack());
            }
            responseObserver.onNext(ApmTestClient.SpanSetErrorReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void flushSpans(ApmTestClient.FlushSpansArgs request, StreamObserver<ApmTestClient.FlushSpansReturn> responseObserver) {
        LOGGER.info("Flushing span: " + request.toString());
        ((InternalTracer) this.tracer).flush();
        this.spans.clear();
        responseObserver.onNext(ApmTestClient.FlushSpansReturn.newBuilder().build());
        responseObserver.onCompleted();
    }

    @Override
    public void flushTraceStats(ApmTestClient.FlushTraceStatsArgs request, StreamObserver<ApmTestClient.FlushTraceStatsReturn> responseObserver) {
        LOGGER.info("Flushing trace stats: " + request.toString());
        ((InternalTracer) this.tracer).flushMetrics();
        responseObserver.onNext(ApmTestClient.FlushTraceStatsReturn.newBuilder().build());
        responseObserver.onCompleted();
    }

    private Span getSpan(long spanId, StreamObserver<?> responseObserver) {
        Span span = this.spans.get(spanId);
        if (span == null) {
            String message = "Span " + spanId + " does not exist.";
            LOGGER.warning(message);
            responseObserver.onError(new IllegalArgumentException(message));
            return null;
        }
        return span;
    }
}
