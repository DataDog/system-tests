package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static com.datadoghq.client.ApmTestClient.DistributedHTTPHeaders;
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
//import static com.datadoghq.client.ApmTestClient.StopTracerArgs;
//import static com.datadoghq.client.ApmTestClient.StopTracerReturn;
import static io.opentracing.propagation.Format.Builtin.TEXT_MAP;

import com.datadoghq.client.APMClientGrpc;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTags;
import datadog.trace.api.DDTraceId;
import datadog.trace.api.internal.InternalTracer;
import io.grpc.stub.StreamObserver;
import io.opentracing.Span;
import io.opentracing.SpanContext;
import io.opentracing.Tracer;
import io.opentracing.propagation.TextMap;
import io.opentracing.tag.Tags;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

public class ApmClientImpl extends APMClientGrpc.APMClientImplBase {
    private final Tracer tracer;
    private final Map<Long, Span> spans;

    public ApmClientImpl(Tracer tracer) {
        this.tracer = tracer;
        this.spans = new HashMap<>();
    }

    @Override
    public void startSpan(StartSpanArgs request, StreamObserver<StartSpanReturn> responseObserver) {
        LOGGER.info("Creating span: " + request.toString());
        // Build span from request
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
        // Extract headers from request to add them to span.
        if (request.hasHttpHeaders()) {
            SpanContext context = tracer.extract(TEXT_MAP, TextMapAdapter.fromRequest(request.getHttpHeaders()));
            builder.asChildOf(context);
        }
        Span span = builder.start();
        // Store span
        long spanId = DDSpanId.from(span.context().toSpanId());
        long traceId = DDTraceId.from(span.context().toTraceId()).toLong();
        this.spans.put(spanId, span);
        // Complete request
        responseObserver.onNext(StartSpanReturn.newBuilder()
                .setSpanId(spanId)
                .setTraceId(traceId)
                .build()
        );
        responseObserver.onCompleted();
    }

    @Override
    public void injectHeaders(InjectHeadersArgs request, StreamObserver<InjectHeadersReturn> responseObserver) {
        LOGGER.info("Inject headers: " + request.toString());
        Span span = getSpan(request.getSpanId(), responseObserver);
        if (span != null) {
            // Get context from span and inject it to carrier
            SpanContext context = span.context();
            TextMapAdapter carrier = TextMapAdapter.empty();
            this.tracer.inject(context, TEXT_MAP, carrier);
            // Copy carrier content to protobuf response
            DistributedHTTPHeaders.Builder headerBuilder = DistributedHTTPHeaders.newBuilder();
            for (Map.Entry<String, String> header : carrier) {
                headerBuilder.putHttpHeaders(header.getKey(), header.getValue());
            }
            // Complete request
            responseObserver.onNext(InjectHeadersReturn.newBuilder()
                    .setHttpHeaders(headerBuilder.build())
                    .build()
            );
            responseObserver.onCompleted();
        }
    }

    @Override
    public void finishSpan(FinishSpanArgs request, StreamObserver<FinishSpanReturn> responseObserver) {
        LOGGER.info("Finishing span: " + request.toString());
        Span span = getSpan(request.getId(), responseObserver);
        if (span != null) {
            span.finish();
            responseObserver.onNext(FinishSpanReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void spanSetMeta(SpanSetMetaArgs request, StreamObserver<SpanSetMetaReturn> responseObserver) {
        LOGGER.info("Setting meta span: " + request.toString());
        Span span = getSpan(request.getSpanId(), responseObserver);
        if (span != null) {
            span.setTag(request.getKey(), request.getValue());
            responseObserver.onNext(SpanSetMetaReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void spanSetMetric(SpanSetMetricArgs request, StreamObserver<SpanSetMetricReturn> responseObserver) {
        LOGGER.info("Setting span metric: " + request.toString());
        Span span = getSpan(request.getSpanId(), responseObserver);
        if (span != null) {
            span.setTag(request.getKey(), request.getValue());
            responseObserver.onNext(SpanSetMetricReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void spanSetError(SpanSetErrorArgs request, StreamObserver<SpanSetErrorReturn> responseObserver) {
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
            responseObserver.onNext(SpanSetErrorReturn.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void flushSpans(FlushSpansArgs request, StreamObserver<FlushSpansReturn> responseObserver) {
        LOGGER.info("Flushing span: " + request.toString());
        ((InternalTracer) this.tracer).flush();
        this.spans.clear();
        responseObserver.onNext(FlushSpansReturn.newBuilder().build());
        responseObserver.onCompleted();
    }

    @Override
    public void flushTraceStats(FlushTraceStatsArgs request, StreamObserver<FlushTraceStatsReturn> responseObserver) {
        LOGGER.info("Flushing trace stats: " + request.toString());
        ((InternalTracer) this.tracer).flushMetrics();
        responseObserver.onNext(FlushTraceStatsReturn.newBuilder().build());
        responseObserver.onCompleted();
    }

//    @Override
//    public void stopTracer(StopTracerArgs request, StreamObserver<StopTracerReturn> responseObserver) {
//        this.tracer.close();
//        responseObserver.onNext(StopTracerReturn.newBuilder().build());
//        responseObserver.onCompleted();
//    }

    private Span getSpan(long spanId, StreamObserver<?> responseObserver) {
        Span span = this.spans.get(spanId);
        if (span == null) {
            String message = "Span " + spanId + " does not exist.";
            LOGGER.warn(message);
            responseObserver.onError(new IllegalArgumentException(message));
            return null;
        }
        return span;
    }

    private static class TextMapAdapter implements TextMap {
        private final Map<String, String> map;

        private static TextMapAdapter empty() {
            return new TextMapAdapter(new HashMap<>());
        }

        private static TextMapAdapter fromRequest(DistributedHTTPHeaders headers) {
            return new TextMapAdapter(headers.getHttpHeadersMap());
        }

        private TextMapAdapter(Map<String, String> map) {
            this.map = map;
        }

        @Override
        public Iterator<Map.Entry<String, String>> iterator() {
            return map.entrySet().iterator();
        }

        @Override
        public void put(String key, String value) {
            map.put(key, value);
        }
    }
}
