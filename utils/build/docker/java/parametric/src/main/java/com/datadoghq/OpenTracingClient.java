package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static io.opentracing.propagation.Format.Builtin.TEXT_MAP;

import com.datadoghq.client.APMClientGrpc;
import com.datadoghq.client.ApmTestClient;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTags;
import datadog.trace.api.DDTraceId;
import io.grpc.stub.StreamObserver;
import io.opentracing.Span;
import io.opentracing.SpanContext;
import io.opentracing.Tracer;
import io.opentracing.propagation.TextMap;
import io.opentracing.tag.Tags;
import io.opentracing.util.GlobalTracer;

import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class OpenTracingClient extends APMClientGrpc.APMClientImplBase {
    private final Tracer tracer;
    private final Map<Long, Span> spans;

    OpenTracingClient() {
        this.tracer = GlobalTracer.get();
        this.spans = new HashMap<>();
    }

    @Override
    public void startSpan(ApmTestClient.StartSpanArgs request, StreamObserver<ApmTestClient.StartSpanReturn> responseObserver) {
        LOGGER.info("Starting OT span: {}", request);
        try {
            // Build span from request
            Tracer.SpanBuilder builder = this.tracer.buildSpan(request.getName());
            if (request.hasService()) {
                builder.withTag(DDTags.SERVICE_NAME, request.getService());
            }
            long parentId = request.hasParentId() ? request.getParentId() : 0;
            if (parentId != 0) { // The parent id can be negative since we have a long representing uint64
                Span parentSpan = getSpan(parentId, responseObserver);
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
            ApmTestClient.DistributedHTTPHeaders httpHeaders = request.hasHttpHeaders() ? request.getHttpHeaders() : null;
            if (httpHeaders != null && httpHeaders.getHttpHeadersCount() > 0) {
                SpanContext context = this.tracer.extract(TEXT_MAP, TextMapAdapter.fromRequest(httpHeaders));
                builder.asChildOf(context);
            }
            // Extract span tags from request to add them to span.
            for (ApmTestClient.HeaderTuple spanTag : request.getSpanTagsList()) {
                builder.withTag(spanTag.getKey(), spanTag.getValue());
            }
            Span span = builder.start();
            // Store span
            long spanId = DDSpanId.from(span.context().toSpanId());
            long traceId = DDTraceId.from(span.context().toTraceId()).toLong();
            this.spans.put(spanId, span);
            // Complete request
            responseObserver.onNext(ApmTestClient.StartSpanReturn.newBuilder()
                    .setSpanId(spanId)
                    .setTraceId(traceId)
                    .build()
            );
            responseObserver.onCompleted();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void finishSpan(ApmTestClient.FinishSpanArgs request, StreamObserver<ApmTestClient.FinishSpanReturn> responseObserver) {
        LOGGER.info("Finishing OT span: {}", request);
        try {
            Span span = getSpan(request.getId(), responseObserver);
            if (span != null) {
                span.finish();
                responseObserver.onNext(ApmTestClient.FinishSpanReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void spanSetMeta(ApmTestClient.SpanSetMetaArgs request, StreamObserver<ApmTestClient.SpanSetMetaReturn> responseObserver) {
        LOGGER.info("Setting meta for OT span: {}", request); // TODO Check if only OT or OTel too?
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                span.setTag(request.getKey(), request.getValue());
                responseObserver.onNext(ApmTestClient.SpanSetMetaReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void spanSetMetric(ApmTestClient.SpanSetMetricArgs request, StreamObserver<ApmTestClient.SpanSetMetricReturn> responseObserver) {
        LOGGER.info("Setting OT span metric: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                span.setTag(request.getKey(), request.getValue());
                responseObserver.onNext(ApmTestClient.SpanSetMetricReturn.newBuilder().build());
                responseObserver.onCompleted();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void spanSetError(ApmTestClient.SpanSetErrorArgs request, StreamObserver<ApmTestClient.SpanSetErrorReturn> responseObserver) {
        LOGGER.info("Setting OT span error: {}", request);
        try {
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
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }
    }

    @Override
    public void injectHeaders(ApmTestClient.InjectHeadersArgs request, StreamObserver<ApmTestClient.InjectHeadersReturn> responseObserver) {
        LOGGER.info("Inject headers context to OT tracer: {}", request);
        try {
            Span span = getSpan(request.getSpanId(), responseObserver);
            if (span != null) {
                // Get context from span and inject it to carrier
                SpanContext context = span.context();
                TextMapAdapter carrier = TextMapAdapter.empty();
                this.tracer.inject(context, TEXT_MAP, carrier);
                // Copy carrier content to protobuf response
                ApmTestClient.DistributedHTTPHeaders.Builder headerBuilder = ApmTestClient.DistributedHTTPHeaders.newBuilder();
                for (Map.Entry<String, String> header : carrier) {
                    headerBuilder.addHttpHeaders(ApmTestClient.HeaderTuple.newBuilder()
                            .setKey(header.getKey())
                            .setValue(header.getValue())
                    );
                }
                // Complete request
                responseObserver.onNext(ApmTestClient.InjectHeadersReturn.newBuilder()
                        .setHttpHeaders(headerBuilder.build())
                        .build()
                );
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
            String message = "OT span " + spanId + " does not exist.";
            LOGGER.warn(message);
            responseObserver.onError(new IllegalArgumentException(message));
            return null;
        }
        return span;
    }

    void clearSpans() {
        this.spans.clear();
    }

    void close() {
        this.tracer.close();
    }

    private static class TextMapAdapter implements TextMap {
        private final List<Map.Entry<String, String>> entries;

        private static TextMapAdapter empty() {
            return new TextMapAdapter(new ArrayList<>());
        }

        private static TextMapAdapter fromRequest(ApmTestClient.DistributedHTTPHeaders headers) {
            return new TextMapAdapter(headers.getHttpHeadersList()
                    .stream()
                    .map(headerTuple -> new AbstractMap.SimpleEntry<>(headerTuple.getKey(), headerTuple.getValue()))
                    .collect(Collectors.toList()));
        }

        private TextMapAdapter(List<Map.Entry<String, String>> entries) {
            this.entries = entries;
        }

        @Override
        public Iterator<Map.Entry<String, String>> iterator() {
            return entries.iterator();
        }

        @Override
        public void put(String key, String value) {
            entries.add(new AbstractMap.SimpleEntry<>(key, value));
        }
    }
}
