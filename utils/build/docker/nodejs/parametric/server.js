'use strict'

const tracer = require('dd-trace').init()
tracer.use('express', false)
tracer.use('http', false)
tracer.use('dns', false)

const SpanContext = require('dd-trace/packages/dd-trace/src/opentracing/span_context')
const OtelSpanContext = require('dd-trace/packages/dd-trace/src/opentelemetry/span_context')

const { trace, ROOT_CONTEXT, SpanKind, propagation } = require('@opentelemetry/api')
const { millisToHrTime } = require('@opentelemetry/core')

const { TracerProvider } = tracer
const tracerProvider = new TracerProvider()
tracerProvider.register()

const express = require('express');

const app = express();
app.use(express.json());

let dummyIdIncrementer = 10000000

function microLongToHrTime (timestamp) {
  if (timestamp === null) {
      return [0, 0]
  }
  return [
      Math.floor(timestamp / 1000000),
      (timestamp % 1000000) * 1000,
  ]
}

const otelStatusCodes = {
  'UNSET': 0,
  'OK': 1,
  'ERROR': 2
}

const otelSpanKinds = {
  0: SpanKind.INTERNAL,
  1: SpanKind.SERVER,
  2: SpanKind.CLIENT,
  3: SpanKind.PRODUCER,
  4: SpanKind.CONSUMER
}

const spans = new Map()
const ddContext = new Map()
const otelSpans = new Map()

app.post('/trace/span/inject_headers', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  const http_headersDict = {};
  const http_headers = [];

  tracer.inject(span, 'http_headers', http_headersDict);
  for (const [key, value] of Object.entries(http_headersDict)) {
      http_headers.push([key, value]);
  }

  res.json({ http_headers });
});

app.post('/trace/span/extract_headers', (req, res) => {
  const request = req.body;
  const http_headers = request.http_headers || [];
  // Node.js HTTP headers are automatically lower-cased, simulate that here.
  const linkHeaders = Object.fromEntries(http_headers.map(([k, v]) => [k.toLowerCase(), v]));
  const extracted = tracer.extract('http_headers', linkHeaders);

  let extractedSpanID = null;
  const dummyTracer = require('dd-trace').init()
  const extractPropagator = dummyTracer._tracer._config.tracePropagationStyle.extract

  if (extractPropagator.includes('baggage') && extracted && !extracted._spanId && !extracted._traceId) {
    // baggage propagation does not require ids so http_headers could contain no ids
    // several endpoints in this file rely on having ids so we need to have dummy ids for internal use
    extracted._spanId = dummyIdIncrementer
    extracted._traceId = dummyIdIncrementer
    dummyIdIncrementer += 1
  }

  if (extracted && extracted._spanId) {
    extractedSpanID = extracted.toSpanId();
    ddContext[extractedSpanID] = extracted;
  }

  res.json({ span_id: extractedSpanID });
});

app.get('/trace/crash', (req, res) => {
  process.kill(process.pid, 'SIGSEGV');
  res.json({});
});

app.post('/trace/span/start', (req, res) => {
  const request = req.body;
  let parent = spans[request.parent_id] || ddContext[request.parent_id];

  const tags = {service: request.service, resource: request.resource};
  for (const [key, value] of request.span_tags) tags[key] = value

  const span = tracer.startSpan(request.name, {
    type: request.type,
    childOf: parent,
    tags
  });

  if (ddContext[request.parent_id]) {
    for (const link of ddContext[request.parent_id]._links || []) span.addLink(link.context, link.attributes)
  }

  spans[span.context().toSpanId()] = span;
  res.json({ span_id: span.context().toSpanId(), trace_id:span.context().toTraceId() });
});

app.post('/trace/span/add_link', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  if (spans[request.parent_id]) {
    span.addLink(spans[request.parent_id].context(), request.attributes)
  } else {
    span.addLink(ddContext[request.parent_id], request.attributes)
  }
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
  ddContext.clear();
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
  // TODO: implement once available in Node.js Tracer
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

app.post('/trace/span/set_baggage', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  span.setBaggageItem(request.key, request.value)
  res.json({});
});

app.get('/trace/span/get_baggage', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  const baggage = span.getBaggageItem(request.key)
  res.json({ baggage });
});

app.get('/trace/span/get_all_baggage', (req, res) => {
const request = req.body;
  const span = spans[request.span_id]
  const baggage = span.getAllBaggageItems()
  res.json({ baggage: JSON.parse(baggage) });
});

app.post('/trace/span/remove_baggage', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  const baggages = span.removeBaggageItem(request.key)
  res.json({});
});

app.post('/trace/span/remove_all_baggage', (req, res) => {
  const request = req.body;
  const span = spans[request.span_id]
  const baggages = span.removeAllBaggageItems()
  res.json({});
});

app.post('/trace/otel/start_span', (req, res) => {
  const request = req.body;
  const otelTracer = tracerProvider.getTracer()

  const makeSpan = (parentContext) => {

    const links = (request.links || []).map(link => {
      let spanContext = otelSpans[link.parent_id].spanContext()
      return {context: spanContext, attributes: link.attributes}
    });

    let kind = null
    if (request.kind != null) {
      kind = request.kind - 1
    }
    const span = otelTracer.startSpan(request.name, {
        type: request.type,
        kind: otelSpanKinds[request.span_kind],
        attributes: request.attributes,
        links,
        startTime: microLongToHrTime(request.timestamp)
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

  makeSpan()
});

app.post('/trace/otel/end_span', (req, res) => {
  const { id, timestamp } = req.body;
  const span_id = `${id}`
  const span = otelSpans[span_id]
  span.end(microLongToHrTime(timestamp))
  res.json({});
});

app.post('/trace/otel/flush', async (req, res) => {
  tracerProvider.forceFlush().then(function() {
    otelSpans.clear()
    res.json({ success: true })
  })
  .catch(function(rej) {
    console.log(rej)
    res.json({ success: false })
  });
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
  const agentUrl = dummyTracer._tracer?._url ||  config?.url
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
      'dd_version': config?.tags?.version !== undefined ? `${config.tags.version}` : 'null',
      'dd_trace_agent_url': agentUrl !== undefined ? agentUrl.toString() : 'null',
      'dd_trace_rate_limit': config?.sampler?.rateLimit !== undefined ? `${config?.sampler?.rateLimit}` : 'null',
      'dd_dogstatsd_host': config?.dogstatsd?.hostname !== undefined ? `${config.dogstatsd.hostname}` : 'null',
      'dd_dogstatsd_port': config?.dogstatsd?.port !== undefined ? `${config.dogstatsd.port}` : 'null',
      'dd_profiling_enabled': config?.profiling?.enabled !== undefined ? `${config.profiling.enabled}` : 'false',
      'dd_data_streams_enabled': config?.dsmEnabled !== undefined ? `${config.dsmEnabled}` : 'null',
      'dd_logs_injection': config?.logInjection !== undefined ? `${config.logInjection}` : 'null',
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

app.post("/trace/otel/otel_set_baggage", (req, res) => {
  const bag = propagation
        .createBaggage()
        .setEntry(req.body.key, { value: req.body.value });
  const context = propagation.setBaggage(ROOT_CONTEXT, bag)
  const value = propagation.getBaggage(context).getEntry(req.body.key).value
  res.json({ value });
});

const port = process.env.APM_TEST_CLIENT_SERVER_PORT;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
