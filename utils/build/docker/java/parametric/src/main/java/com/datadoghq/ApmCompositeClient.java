package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static com.datadoghq.client.ApmTestClient;
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

import com.datadoghq.client.APMClientHttp;
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

public class ApmCompositeClient extends APMClientHttp.APMClientImplBase {
    private final Tracer ddTracer;
    private final OpenTracingClient otClient;
    private final OpenTelemetryClient otelClient;

    public ApmCompositeClient() {
        this.ddTracer = GlobalTracer.get();
        this.otClient = new OpenTracingClient();
        this.otelClient = new OpenTelemetryClient();
    }

    @Override
    public ApmTestClient.StartSpanReturn startSpan(ApmTestClient.StartSpanArgs request) {
        return this.otClient.startSpan(request);
    }

    @Override
    public ApmTestClient.FinishSpanReturn finishSpan(ApmTestClient.FinishSpanArgs request) {
        return this.otClient.finishSpan(request);
    }

    @Override
    public ApmTestClient.SpanSetMetaReturn spanSetMeta(ApmTestClient.SpanSetMetaArgs request) {
        return this.otClient.spanSetMeta(request);
    }

    @Override
    public ApmTestClient.SpanSetMetricReturn spanSetMetric(ApmTestClient.SpanSetMetricArgs request) {
        return this.otClient.spanSetMetric(request);
    }

    @Override
    public ApmTestClient.SpanSetErrorReturn spanSetError(ApmTestClient.SpanSetErrorArgs request) {
        return this.otClient.spanSetError(request);
    }

    @Override
    public ApmTestClient.InjectHeadersReturn injectHeaders(ApmTestClient.InjectHeadersArgs request) {
        return this.otClient.injectHeaders(request);
    }

    @Override
    public ApmTestClient.FlushSpansReturn flushSpans(ApmTestClient.FlushSpansArgs request) {
        LOGGER.info("Flushing OT spans: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flush();
            this.otClient.clearSpans();
            return FlushSpansReturn.newBuilder().build();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            // TODO : throw error
        }
    }

    @Override
    public ApmTestClient.FlushTraceStatsReturn flushTraceStats(ApmTestClient.FlushTraceStatsArgs request) {
        LOGGER.info("Flushing OT trace stats: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flushMetrics();
            return FlushTraceStatsReturn.newBuilder().build();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            // TODO : throw error
        }
    }

    @Override
    public ApmTestClient.OtelStartSpanReturn otelStartSpan(ApmTestClient.OtelStartSpanArgs request) {
        return this.otelClient.otelStartSpan(request);
    }

    @Override
    public ApmTestClient.OtelEndSpanReturn otelEndSpan(ApmTestClient.OtelEndSpanArgs request) {
        return this.otelClient.otelEndSpan(request);
    }

    @Override
    public ApmTestClient.OtelIsRecordingReturn otelIsRecording(ApmTestClient.OtelIsRecordingArgs request) {
        return this.otelClient.otelIsRecording(request);
    }

    @Override
    public ApmTestClient.OtelSpanContextReturn otelSpanContext(ApmTestClient.OtelSpanContextArgs request) {
        return this.otelClient.otelSpanContext(request);
    }

    @Override
    public ApmTestClient.OtelSetStatusReturn otelSetStatus(ApmTestClient.OtelSetStatusArgs request) {
        return this.otelClient.otelSetStatus(request);
    }

    @Override
    public ApmTestClient.OtelSetNameReturn otelSetName(ApmTestClient.OtelSetNameArgs request) {
        return this.otelClient.otelSetName(request);
    }

    @Override
    public ApmTestClient.OtelSetAttributesReturn otelSetAttributes(ApmTestClient.OtelSetAttributesArgs request) {
        return this.otelClient.otelSetAttributes(request);
    }

    @Override
    public ApmTestClient.OtelFlushSpansReturn otelFlushSpans(ApmTestClient.OtelFlushSpansArgs request) {
        LOGGER.info("Flushing OTel spans: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flush();
            this.otelClient.clearSpans();
            return OtelFlushSpansReturn.newBuilder().setSuccess(true).build();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            // TODO : throw error
        }
    }

    @Override
    public ApmTestClient.OtelFlushTraceStatsReturn otelFlushTraceStats(ApmTestClient.OtelFlushTraceStatsArgs request) {
        LOGGER.info("Flushing OTel trace stats: {}", request);
        try {
            ((InternalTracer) this.ddTracer).flushMetrics();
            return OtelFlushTraceStatsReturn.newBuilder().build();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            // TODO : throw error
        }
    }

    @Override
    public ApmTestClient.StopTracerReturn stopTracer(ApmTestClient.StopTracerArgs request) {
        // Closing OT tracer also close internal DD tracer
        this.otClient.close();
        return StopTracerReturn.newBuilder().build();
    }
}
