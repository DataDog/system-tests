'use strict'

const tracer = require('dd-trace').init()
tracer.use('express', false)
tracer.use('http', false)
tracer.use('dns', false)

const SpanContext = require('dd-trace/packages/dd-trace/src/opentracing/span_context')
const OtelSpanContext = require('dd-trace/packages/dd-trace/src/opentelemetry/span_context')

const { trace, ROOT_CONTEXT } = require('@opentelemetry/api')
const { millisToHrTime } = require('@opentelemetry/core')

const { TracerProvider } = tracer
const tracerProvider = new TracerProvider()
tracerProvider.register()

const express = require('express');

const app = express();
app.use(express.json());


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

const spans = new Map()
const otelSpans = new Map()

// Endpoint /trace/span/inject_headers
app.post('/trace/span/inject_headers', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  const http_headersDict = {}
  const http_headers = []

  tracer.inject(span, 'http_headers', http_headersDict)
  for (const [key, value] of Object.entries(http_headersDict)) {
      http_headers.push([key, value])
  }

  res.json({ http_headers });
});

// Additional Endpoints
app.post('/trace/span/start', (req, res) => {
  const request = req.body;
  let parent

  if (request.parent_id) parent = spans[request.parent_id]

  if (request.origin) {
      const traceId = parent?.traceId
      const parentId = parent?.parentId

      parent = new SpanContext({
          traceId,
          parentId
      })
      parent.origin = request.origin
  }

  const http_headers = request.http_headers || []
  // Node.js HTTP headers are automatically lower-cased, simulate that here.
  const convertedHeaders = {}
  for (const [key, value] of http_headers) {
      convertedHeaders[key.toLowerCase()] = value
  }

  const extracted = tracer.extract('http_headers', convertedHeaders)
  if (extracted !== null) parent = extracted

  const tags = { service: request.service }
  for (const [key, value] of request.span_tags) tags[key] = value

  const span = tracer.startSpan(request.name, {
    type: request.type,
    resource: request.resource,
    childOf: parent,
    tags
  })

  for (const link of request.links || []) {
    const linkParentId = link.parent_id;
    if (linkParentId) {
      const linkParentSpan = spans[linkParentId];
      span.addLink(linkParentSpan.context(), link.attributes);
    } else {
      const linkHeaders = link.http_headers || {};
      const convertedLinkHeaders = {}
      for (const [key, value] of linkHeaders) {
        convertedLinkHeaders[key.toLowerCase()] = value
      }
      const linkExtracted = tracer.extract('http_headers', convertedLinkHeaders);
      if (linkExtracted) {
        span.addLink(linkExtracted, link.attributes);
      }
    }
  }

  spans[span.context().toSpanId()] = span
  res.json({ span_id: span.context().toSpanId(), trace_id:span.context().toTraceId(), service:request.service, resource:request.resource,});
});

app.post('/trace/span/add_link', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  const linked_span = spans[request.parent_id]
  span.addLink(linked_span.context(), request.attributes)
  res.json({});
});

app.post('/trace/span/finish', (req, res) => {
  const id = req.body.span_id
  const span = spans[id]
  span.finish()
  res.json({});
});

app.post('/trace/span/flush', (req, res) => {
  const { _tracer: { _exporter: { _writer } } } = tracer
  _writer.flush(() => {
    res.json({});
  })
  spans.clear();
});

app.post('/trace/span/set_meta', (req, res) => {
  const args = req.body;
  const spanId = args.span_id;
  const key = args.key;
  const value = args.value;
  const span = spans[spanId]
  span.setTag(key, value)
  res.json({});
});

app.post('/trace/span/set_metric', (req, res) => {
  const args = req.body;
  const spanId = args.span_id;
  const key = args.key;
  const value = args.value;
  const span = spans[spanId];
  span.setTag(key, value);
  res.json({});
});

app.post('/trace/stats/flush', (req, res) => {
  // TODO: implement once available in NodeJS Tracer
  res.json({});
});

app.post('/trace/span/error', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  span.addTags({
      'error.msg': request.message,
      'error.type': request.type,
      'error.stack': request.stack
  })
  res.json({});
});

app.post('/trace/otel/start_span', (req, res) => {
  const request = req.body;
  const otelTracer = tracerProvider.getTracer()

  const makeSpan = (parentContext) => {

    const links = (request.links || []).map(link => {
      let spanContext;
      if (link.parent_id && link.parent_id !== 0) {
        spanContext = otelSpans[link.parent_id].spanContext();
      } else {
        const linkHeaders = Object.fromEntries(link.http_headers.map(([k, v]) => [k.toLowerCase(), v]));
        const extractedContext = tracer.extract('http_headers', linkHeaders)
        spanContext = new OtelSpanContext(extractedContext)
      }
      return {context: spanContext, attributes: link.attributes}
    });

    const span = otelTracer.startSpan(request.name, {
        type: request.type,
        kind: request.kind,
        attributes: request.attributes,
        links,
        startTime: nanoLongToHrTime(request.timestamp)
    }, parentContext)
    const ctx = span._ddSpan.context()
    const span_id = ctx._spanId.toString(10)
    const trace_id = ctx._traceId.toString(10)

    otelSpans[span_id] = span
    res.json({ span_id, trace_id });
  }
  if (request.parent_id && request.parent_id !== 0) {
      const parentSpan = otelSpans[request.parent_id]
      const parentContext = trace.setSpan(ROOT_CONTEXT, parentSpan)
      return makeSpan(parentContext)
  }
  if (request.http_headers) {
      const http_headers = request.http_headers || []
      // Node.js HTTP headers are automatically lower-cased, simulate that here.
      const convertedHeaders = {}
      for (const [ key, value ] of http_headers) {
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
});

app.post('/trace/otel/end_span', (req, res) => {
  const { id, timestamp } = req.body;
  const span_id = `${id}`
  const span = otelSpans[span_id]
  span.end(nanoLongToHrTime(timestamp))
  res.json({});
});

app.post('/trace/otel/flush', async (req, res) => {
  await tracerProvider.forceFlush()
  spans.clear();
  otelSpans.clear();
  res.json({ success: true });
});

app.post('/trace/otel/is_recording', (req, res) => {
  const { span_id } = req.body;
  const span = otelSpans[span_id]
  res.json({ is_recording: span.isRecording() });
});

app.post('/trace/otel/span_context', (req, res) => {
  const { span_id } = req.body;
  const span = otelSpans[span_id]
  const ctx = span.spanContext()
  res.json({
    span_id: ctx.spanId,
    trace_id: ctx.traceId,
    // Node.js official OTel API uses a number, not a string
    trace_flags: `0${ctx.traceFlags}`,
    trace_state: ctx.traceState.serialize(),

    // TODO: What is this and where is it supposed to come from? 🤔
    remote: ctx.is_remote?ctx.is_remote:false,
  });
});

app.post('/trace/otel/set_status', (req, res) => {
  const { span_id, code, description } = req.body;
  const span = otelSpans[span_id]
  span.setStatus({
      code: otelStatusCodes[code],
      message: description
  })
  res.json({});
});

app.post('/trace/otel/set_name', (req, res) => {
  const { span_id, name } = req.body;
  const span = otelSpans[span_id]
  span.updateName(name)
  res.json({});
});

app.post('/trace/otel/set_attributes', (req, res) => {
  const { span_id, attributes } = req.body;
  const span = otelSpans[span_id]
  span.setAttributes(attributes)
  res.json({});
});

app.get('/trace/config', (req, res) => {
  const dummyTracer = require('dd-trace').init()
  const config = dummyTracer._tracer._config
  res.json( {
    config: {
      'dd_service': config?.service !== undefined ? `${config.service}`.toLowerCase() : 'null',
      'dd_log_level': config?.logLevel !== undefined ? `${config.logLevel}`.toLowerCase() : 'null',
      'dd_trace_debug': config?.debug !== undefined ? `${config.debug}`.toLowerCase() : 'null',
      'dd_trace_sample_rate': config?.sampleRate !== undefined ? `${config.sampleRate}` : 'null',
      'dd_trace_enabled': config ? 'true' : 'false', // in node if dd_trace_enabled is true the tracer won't have a config object
      'dd_runtime_metrics_enabled': config?.runtimeMetrics !== undefined ? `${config.runtimeMetrics}`.toLowerCase() : 'null',
      'dd_tags': config?.tags !== undefined ? Object.entries(config.tags).map(([key, val]) => `${key}:${val}`).join(',') : 'null',
      'dd_trace_propagation_style': config?.tracePropagationStyle?.inject.join(',') ?? 'null',
      'dd_trace_sample_ignore_parent': 'null', // not implemented in node
      'dd_trace_otel_enabled': 'null', // not exposed in config object in node
      'dd_env': config?.tags?.env !== undefined ? `${config.tags.env}` : 'null',
      'dd_version': config?.tags?.version !== undefined ? `${config.tags.version}` : 'null'
    }
  });
});

app.post("/trace/otel/add_event", (req, res) => {
  const { span_id, name, timestamp, attributes } = req.body;
  const span = otelSpans[span_id]
  // convert to TimeInput object using millisToHrTime
  span.addEvent(name, attributes, millisToHrTime(timestamp / 1000))
  res.json({})
})

app.post("/trace/otel/record_exception", (req, res) => {
  const { span_id, message, attributes } = req.body;
  const span = otelSpans[span_id]
  span.recordException(new Error(message))
  res.json({})
})

// TODO: implement this endpoint correctly, current blockers:
// 1. Fails on invalid url
// 2. does not generate span, because http instrumentation turned off

// app.post('/http/client/request', (req, res) => {
//     const http = require('http')

//         const options = {
//             method: req.method,
//             headers: req.headers
//         }
//         const request = http.request(req.url, options, response => {
//             response.on('data', () => {})
//             response.on('end', () => callback(null, { statusCode: response.statusCode }))
//         })
//         request.on('error', e => callback(e))
//         request.write(JSON.stringify(req.body))
//         request.end()
//         res.json({});
//     }

//   );

const port = process.env.APM_TEST_CLIENT_SERVER_PORT;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
