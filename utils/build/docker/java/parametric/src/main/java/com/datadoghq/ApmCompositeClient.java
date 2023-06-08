package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static com.datadoghq.client.ApmTestClient.FinishSpanArgs;
import static com.datadoghq.client.ApmTestClient.FinishSpanReturn;
import static com.datadoghq.client.ApmTestClient.FlushSpansArgs;
import static com.datadoghq.client.ApmTestClient.FlushSpansReturn;
import static com.datadoghq.client.ApmTestClient.FlushTraceStatsArgs;
import static com.datadoghq.client.ApmTestClient.FlushTraceStatsReturn;
import static com.datadoghq.client.ApmTestClient.InjectHeadersArgs;
import static com.datadoghq.client.ApmTestClient.InjectHeadersReturn;
import static com.datadoghq.client.ApmTestClient.SpanSetErrorArgs;
import static com.datadoghq.client.ApmTestClient.SpanSetErrorReturn;
import static com.datadoghq.client.ApmTestClient.SpanSetMetaArgs;
import static com.datadoghq.client.ApmTestClient.SpanSetMetaReturn;
import static com.datadoghq.client.ApmTestClient.SpanSetMetricArgs;
import static com.datadoghq.client.ApmTestClient.SpanSetMetricReturn;
import static com.datadoghq.client.ApmTestClient.StartSpanArgs;
import static com.datadoghq.client.ApmTestClient.StartSpanReturn;

import com.datadoghq.client.APMClientGrpc;
import com.datadoghq.client.ApmTestClient;
import com.datadoghq.client.ApmTestClient.OtelEndSpanArgs;
import com.datadoghq.client.ApmTestClient.OtelEndSpanReturn;
import com.datadoghq.client.ApmTestClient.OtelFlushSpansArgs;
import com.datadoghq.client.ApmTestClient.OtelFlushSpansReturn;
import com.datadoghq.client.ApmTestClient.OtelFlushTraceStatsArgs;
import com.datadoghq.client.ApmTestClient.OtelFlushTraceStatsReturn;
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
import com.datadoghq.client.ApmTestClient.StopTracerReturn;
import datadog.trace.api.GlobalTracer;
import datadog.trace.api.Tracer;
import datadog.trace.api.internal.InternalTracer;
import io.grpc.stub.StreamObserver;

public class ApmCompositeClient extends APMClientGrpc.APMClientImplBase {
    private final Tracer ddTracer;
    private final OpenTracingClient otClient;
    private final OpenTelemetryClient otelClient;

    public ApmCompositeClient() {
        this.ddTracer = GlobalTracer.get();
        this.otClient = new OpenTracingClient();
        this.otelClient = new OpenTelemetryClient();
    }

    @Override
    public void startSpan(StartSpanArgs request, StreamObserver<StartSpanReturn> responseObserver) {
        this.otClient.startSpan(request, responseObserver);
    }

    @Override
    public void finishSpan(FinishSpanArgs request, StreamObserver<FinishSpanReturn> responseObserver) {
        this.otClient.finishSpan(request, responseObserver);
    }

    @Override
    public void spanSetMeta(SpanSetMetaArgs request, StreamObserver<SpanSetMetaReturn> responseObserver) {
        this.otClient.spanSetMeta(request, responseObserver);
    }

    @Override
    public void spanSetMetric(SpanSetMetricArgs request, StreamObserver<SpanSetMetricReturn> responseObserver) {
        this.otClient.spanSetMetric(request, responseObserver);
    }

    @Override
    public void spanSetError(SpanSetErrorArgs request, StreamObserver<SpanSetErrorReturn> responseObserver) {
        this.otClient.spanSetError(request, responseObserver);
    }

    @Override
    public void injectHeaders(InjectHeadersArgs request, StreamObserver<InjectHeadersReturn> responseObserver) {
        this.otClient.injectHeaders(request, responseObserver);
    }

    @Override
    public void flushSpans(FlushSpansArgs request, StreamObserver<FlushSpansReturn> responseObserver) {
        LOGGER.info("Flushing OT spans: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flush();
            this.otClient.clearSpans();
            responseObserver.onNext(FlushSpansReturn.newBuilder().build());
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void flushTraceStats(FlushTraceStatsArgs request, StreamObserver<FlushTraceStatsReturn> responseObserver) {
        LOGGER.info("Flushing OT trace stats: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flushMetrics();
            responseObserver.onNext(FlushTraceStatsReturn.newBuilder().build());
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelStartSpan(OtelStartSpanArgs request, StreamObserver<OtelStartSpanReturn> responseObserver) {
        this.otelClient.otelStartSpan(request, responseObserver);
    }

    @Override
    public void otelEndSpan(OtelEndSpanArgs request, StreamObserver<OtelEndSpanReturn> responseObserver) {
        this.otelClient.otelEndSpan(request, responseObserver);
    }

    @Override
    public void otelIsRecording(OtelIsRecordingArgs request, StreamObserver<OtelIsRecordingReturn> responseObserver) {
        this.otelClient.otelIsRecording(request, responseObserver);
    }

    @Override
    public void otelSpanContext(OtelSpanContextArgs request, StreamObserver<OtelSpanContextReturn> responseObserver) {
        this.otelClient.otelSpanContext(request, responseObserver);
    }

    @Override
    public void otelSetStatus(OtelSetStatusArgs request, StreamObserver<OtelSetStatusReturn> responseObserver) {
        this.otelClient.otelSetStatus(request, responseObserver);
    }

    @Override
    public void otelSetName(OtelSetNameArgs request, StreamObserver<OtelSetNameReturn> responseObserver) {
        this.otelClient.otelSetName(request, responseObserver);
    }

    @Override
    public void otelSetAttributes(OtelSetAttributesArgs request, StreamObserver<OtelSetAttributesReturn> responseObserver) {
        this.otelClient.otelSetAttributes(request, responseObserver);
    }

    @Override
    public void otelFlushSpans(OtelFlushSpansArgs request, StreamObserver<OtelFlushSpansReturn> responseObserver) {
        LOGGER.info("Flushing OTel spans: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flush();
            this.otelClient.clearSpans();
            responseObserver.onNext(OtelFlushSpansReturn.newBuilder().setSuccess(true).build());
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void otelFlushTraceStats(OtelFlushTraceStatsArgs request, StreamObserver<OtelFlushTraceStatsReturn> responseObserver) {
        LOGGER.info("Flushing OTel trace stats: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flushMetrics();
            responseObserver.onNext(OtelFlushTraceStatsReturn.newBuilder().build());
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void stopTracer(ApmTestClient.StopTracerArgs request, StreamObserver<StopTracerReturn> responseObserver) {
        // Closing OT tracer also close internal DD tracer
        this.otClient.close();
        responseObserver.onNext(StopTracerReturn.newBuilder().build());
        responseObserver.onCompleted();
    }
}
