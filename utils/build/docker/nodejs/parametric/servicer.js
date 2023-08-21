'use strict'

const tracer = require('dd-trace').init()
tracer.use('dns', false)

const SpanContext = require('dd-trace/packages/dd-trace/src/opentracing/span_context')
const OtelSpanContext = require('dd-trace/packages/dd-trace/src/opentelemetry/span_context')

const { trace, ROOT_CONTEXT } = require('@opentelemetry/api')

const { TracerProvider } = tracer
const tracerProvider = new TracerProvider()
tracerProvider.register()

function buildAttrs (attributes) {
    const attrs = {}
    for (const [key, value] of Object.entries(attributes.key_vals)) {
        attrs[key] = value.val[0][value.val[0].val]
    }
    return attrs
}

function nanoLongToHrTime ({ high = 0, low = 0 } = {}) {
    return [
        high * 1e3 + Math.floor(low / 1e6),
        (low % 1e6) * 1e3,
    ]
}

const otelStatusCodes = {
    'UNSET': 0,
    'OK': 1,
    'ERROR': 2
}

class Servicer {
    spans = {}
    otelSpans = {}

    StartSpan = (call, callback) => {
        const { request } = call
        let parent

        if (request.parent_id) parent = this.spans[request.parent_id]

        if (request.origin) {
            const traceId = parent?.traceId
            const parentId = parent?.parentId

            parent = new SpanContext({
                traceId,
                parentId
            })
            parent.origin = request.origin
        }

        const http_headers = request.http_headers.http_headers || []
        // Node.js HTTP headers are automatically lower-cased, simulate that here.
        const convertedHeaders = {}
        for (const { key, value } of http_headers) {
            convertedHeaders[key.toLowerCase()] = value
        }
        const extracted = tracer.extract('http_headers', convertedHeaders)
        if (extracted !== null) parent = extracted

        const span = tracer.startSpan(request.name, {
            type: request.type,
            childOf: parent,
            tags: {
                service: request.service,
                "resource.name": request.resource
            }
        })

        this.spans[span.context().toSpanId()] = span

        return callback(null, {
            span_id: span.context().toSpanId(),
            trace_id: span.context().toTraceId()
        })
    }

    InjectHeaders = (call, callback) => {
        const { request } = call
        const span = this.spans[request.span_id]
        const http_headersDict = {}
        const http_headers = []

        tracer.inject(span, 'http_headers', http_headersDict)
        for (const [key, value] of Object.entries(http_headersDict)) {
            http_headers.push({key: key, value: value})
        }

        return callback(null, {
            http_headers: { http_headers }
        })
    }

    SpanSetMeta = (call, callback) => {
        const span = this.spans[call.request.span_id]
        span.setTag(call.request.key, call.request.value)
        return callback(null, {})
    }

    // dd-trace-js has support for numeric values in tags
    SpanSetMetric = (call, callback) => {
        return this.SpanSetMeta(call, callback)
    }

    SpanSetError = (request, callback) => {
        const span = this.spans[request.span_id]
        span.addTags({
            'error.msg': request.message,
            'error.type': request.type,
            'error.stack': request.stack
        })
        return callback(null, {})
    }

    FinishSpan = (call, callback) => {
        const { id } = call.request
        const span = this.spans[id]
        span.finish()
        delete this.spans[id]
        return callback(null, {})

    }

    FlushSpans = (_, callback) => {
        const { _tracer: { _exporter: { _writer } } } = tracer
        _writer.flush(() => {
            callback(null, {})
        })

    }

    FlushTraceStats = (_, callback) => {
        // TODO: implement once available in NodeJS Tracer
        return callback(null, {})
    }

    StopTracer = (_, callback) => {
        return callback(null, {})
    }

    OtelStartSpan = (call, callback) => {
        const { request } = call

        const otelTracer = tracerProvider.getTracer()

        const makeSpan = (parentContext) => {
            try {
                const span = otelTracer.startSpan(request.name, {
                    type: request.type,
                    kind: request.kind,
                    attributes: buildAttrs(request.attributes),
                    startTime: nanoLongToHrTime(request.timestamp)
                }, parentContext)

                const ctx = span._ddSpan.context()
                const span_id = ctx._spanId.toString(10)
                const trace_id = ctx._traceId.toString(10)

                this.otelSpans[span_id] = span

                return callback(null, {
                    span_id,
                    trace_id
                })
            } catch (err) {
                callback(err)
            }
        }

        if (request.parent_id && !request.parent_id.isZero()) {
            const parentSpan = this.otelSpans[request.parent_id]
            const parentContext = trace.setSpan(ROOT_CONTEXT, parentSpan)
            return makeSpan(parentContext)
        }

        if (request.http_headers) {
            const http_headers = request.http_headers.http_headers || []
            // Node.js HTTP headers are automatically lower-cased, simulate that here.
            const convertedHeaders = {}
            for (const { key, value } of http_headers) {
                convertedHeaders[key.toLowerCase()] = value
            }
            const extracted = tracer.extract('http_headers', convertedHeaders)
            if (extracted) {
                const parentSpan = trace.wrapSpanContext(new OtelSpanContext(extracted))
                const parentContext = trace.setSpan(ROOT_CONTEXT, parentSpan)
                return makeSpan(parentContext)
            }
        }

        makeSpan()
    }

    OtelEndSpan = (call, callback) => {
        const { id, timestamp } = call.request
        const span_id = `${id}`
        const span = this.otelSpans[span_id]
        span.end(nanoLongToHrTime(timestamp))
        // NOTE: Do not cleanup otelSpans here because we want to be able
        // to test behaviour of methods on already completed spans.
        return callback(null, {})

    }

    OtelIsRecording = (call, callback) => {
        const { span_id } = call.request
        const span = this.otelSpans[span_id]
        return callback(null, {
            is_recording: span.isRecording()
        })

    }

    OtelSpanContext = (call, callback) => {
        const { span_id } = call.request
        const span = this.otelSpans[span_id]
        const ctx = span.spanContext()
        return callback(null, {
            span_id: ctx.spanId,
            trace_id: ctx.traceId,
            // Node.js official OTel API uses a number, not a string
            trace_flags: `0${ctx.traceFlags}`,
            trace_state: ctx.traceState.serialize(),

            // TODO: What is this and where is it supposed to come from? 🤔
            remote: ctx.is_remote,
        })

    }

    OtelSetStatus = (call, callback) => {
        const { span_id, code, description } = call.request
        const span = this.otelSpans[span_id]
        span.setStatus({
            code: otelStatusCodes[code],
            message: description
        })
        return callback(null, {})

    }

    OtelSetName = (call, callback) => {
        const { span_id, name } = call.request
        const span = this.otelSpans[span_id]
        span.updateName(name)
        return callback(null, {})

    }

    OtelSetAttributes = (call, callback) => {
        const { span_id, attributes } = call.request
        const span = this.otelSpans[span_id]
        span.setAttributes(buildAttrs(attributes))
        return callback(null, {})

    }

    OtelFlushSpans = async (call, callback) => {
        await tracerProvider.forceFlush()
        this.spans = {}
        this.otelSpans = {}
        return callback(null, {
            success: true
        })

    }

}

module.exports = Servicer
