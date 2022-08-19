'use strict'

const tracer = require('dd-trace').init()
const SpanContext = require('dd-trace/packages/dd-trace/src/opentracing/span_context');

class Servicer {
    constructor() {
        this.spans = {};
    }

    StartSpan (request, callback) {

        let parent;

        if (request.parent_id) parent = this.spans[request.parent_id];

        if (request.origin) {
            const traceId = parent?.traceId;
            const parentId = parent?.parentId;

            parent = new SpanContext({
                traceId,
                parentId
            });
            parent.origin = request.origin;
        }

        const span = tracer.startSpan(request.name, {
            service: request.service, 
            type: request.type,
            resource: request.resource,
            childOf: parent,
        });

        this.spans[span.spanId] = span;

        return callback(null, {
            span_id: span.context()._spanId,
            trace_id: span.context()._traceId
        });
    }

    SetTag (request, callback) {
        const span = this.spans[request.span_id];
        span.setTag(request.key, request.value);
        return callback(null, {})

    }

    SpanSetError (request, callback) {
        const span = this.spans[request.span_id];
        span.addTags({
            'error.msg': request.message,
            'error.type': request.type,
            'error.stack': request.stack
        });
        span.error = 1;
        return callback(null, {})
    }

    FinishSpan (request, callback) {
        const { id } = request;
        const span = this.spans[id];
        delete this.spans[id];
        span.finish();
        return callback(null, {})

    }

    FlushSpans (_, callback) {
        const { _tracer: { _exporter: { _writer } } } = tracer;
        _writer.flush();
        return callback(null, {})

    }

    FlushTraceStats (_, callback) {
        // TODO: implement once available in NodeJS Tracer
        return callback(null, {})
    }
}

module.exports = Servicer;