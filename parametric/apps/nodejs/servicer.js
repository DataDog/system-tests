'use strict'

const tracer = require('dd-trace').init()
tracer.use('dns', false)
const SpanContext = require('dd-trace/packages/dd-trace/src/opentracing/span_context');

class Servicer {
    constructor() {
        this.spans = {};
    }

    StartSpan = (call, callback) => {
        const { request } = call;
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

        const http_headers = request.http_headers.http_headers || [];
        // Node.js HTTP headers are automatically lower-cased, simulate that here.
        const convertedHeaders = {};
        for (const { key, value } of http_headers) {
            convertedHeaders[key.toLowerCase()] = value;
        }
        const extracted = tracer.extract('http_headers', convertedHeaders);
        if (extracted !== null) parent = extracted;

        const span = tracer.startSpan(request.name, {
            type: request.type,
            resource: request.resource,
            childOf: parent,
            tags: {
                service: request.service
            }
        });

        this.spans[span.context().toSpanId()] = span;

        return callback(null, {
            span_id: span.context().toSpanId(),
            trace_id: span.context().toTraceId()
        });
    }

    InjectHeaders = (call, callback) => {
        const { request } = call;
        const span = this.spans[request.span_id];
        const http_headersDict = {};
        const http_headers = [];

        tracer.inject(span, 'http_headers', http_headersDict);
        for (const [key, value] of Object.entries(http_headersDict)) {
            http_headers.push({key: key, value: value});
        }

        return callback(null, {
            http_headers: { http_headers }
        });
    }

    SetTag = (call, callback) => {
        const span = this.spans[call.request.span_id];
        span.setTag(call.request.key, call.request.value);
        return callback(null, {})

    }

    SpanSetError = (request, callback) => {
        const span = this.spans[request.span_id];
        span.addTags({
            'error.msg': request.message,
            'error.type': request.type,
            'error.stack': request.stack
        });
        return callback(null, {})
    }

    FinishSpan = (call, callback) => {
        const { id } = call.request;
        const span = this.spans[id];
        span.finish();
        delete this.spans[id];
        return callback(null, {})

    }

    FlushSpans = (_, callback) => {
        const { _tracer: { _exporter: { _writer } } } = tracer;
        _writer.flush();
        return callback(null, {})

    }

    FlushTraceStats = (_, callback) => {
        // TODO: implement once available in NodeJS Tracer
        return callback(null, {})
    }

    StopTracer = (_, callback) => {
        return callback(null, {})
    }
}

module.exports = Servicer;
