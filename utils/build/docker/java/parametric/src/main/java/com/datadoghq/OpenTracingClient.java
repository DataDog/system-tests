package com.datadoghq;

import static com.datadoghq.App.LOGGER;
import static io.opentracing.propagation.Format.Builtin.TEXT_MAP;

import com.datadoghq.client.APMClientHttp;
import com.datadoghq.client.ApmTestClient;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.DDTags;
import datadog.trace.api.DDTraceId;
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

public class OpenTracingClient extends APMClientHttp.APMClientImplBase {
    private final Tracer tracer;
    private final Map<Long, Span> spans;

    OpenTracingClient() {
        this.tracer = GlobalTracer.get();
        this.spans = new HashMap<>();
    }

    @Override
    public ApmTestClient.StartSpanReturn startSpan(@RequestBody ApmTestClient.StartSpanArgs request) {
        LOGGER.info("Starting OT span: {}", request);
        try {
            // Build span from request
            Tracer.SpanBuilder builder = this.tracer.buildSpan(request.getName());
            if (request.hasService()) {
                builder.withTag(DDTags.SERVICE_NAME, request.getService());
            }
            long parentId = request.hasParentId() ? request.getParentId() : 0;
            if (parentId != 0) { // The parent id can be negative since we have a long representing uint64
                Span parentSpan = getSpan(parentId);
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
            ApmTestClient.StartSpanReturn result = ApmTestClient.StartSpanReturn.newBuilder()
                .setSpanId(spanId)
                .setTraceId(traceId)
                .build();
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
            responseObserver.onError(t);
        }

        return result;
    }

    @Override
    public ApmTestClient.FinishSpanReturn finishSpan(@RequestBody ApmTestClient.FinishSpanArgs request) {
        LOGGER.info("Finishing OT span: {}", request);
        try {
            Span span = getSpan(request.getId(), responseObserver);
            if (span != null) {
                span.finish();
                return ApmTestClient.FinishSpanReturn.newBuilder().build();
            }
        } catch (Throwable t) {
            LOGGER.error("Uncaught throwable", t);
        }
    }

    @Override
    public ApmTestClient.SpanSetMetaReturn spanSetMeta(@RequestBody ApmTestClient.SpanSetMetaArgs request) {
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
    public ApmTestClient.SpanSetMetricReturn spanSetMetric(@RequestBody ApmTestClient.SpanSetMetricArgs request) {
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
    public ApmTestClient.SpanSetErrorReturn spanSetError(@RequestBody ApmTestClient.SpanSetErrorArgs request) {
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
    public ApmTestClient.InjectHeadersReturn injectHeaders(@RequestBody ApmTestClient.InjectHeadersArgs request) {
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

    private Span getSpan(long spanId) {
        Span span = this.spans.get(spanId);
        if (span == null) {
            String message = "OT span " + spanId + " does not exist.";
            LOGGER.warn(message);
            // Probably we should throw an exception here
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
