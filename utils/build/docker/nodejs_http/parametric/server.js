const express = require('express');
const bodyParser = require('body-parser');
const { NodeTracerProvider } = require('@opentelemetry/node');
const { BatchSpanProcessor } = require('@opentelemetry/tracing');
const { ZipkinExporter } = require('@opentelemetry/exporter-zipkin');
const { diag, context, trace } = require('@opentelemetry/api');
const { SimpleSpanProcessor } = require('@opentelemetry/tracing');
const { HttpTraceContext } = require('@opentelemetry/core');
const { NodeSDK } = require('dd-trace');
const sdk = new NodeSDK({
  tracer: new NodeTracerProvider({
    plugins: {
      express: { enabled: true, path: '@opentelemetry/plugin-express' },
      http: { enabled: true, path: '@opentelemetry/plugin-http' },
    },
  }).getTracer('opentelemetry-plugin', '0.1'),
});
sdk.start();

const app = express();
app.use(bodyParser.json());

const spans = {};
const otelSpans = {};

// Endpoint /trace/span/inject_headers
app.post('/trace/span/inject_headers', (req, res) => {
  const spanId = req.body.span_id;
  const ctx = spans[spanId].context();
  const headers = {};
  HttpTraceContext.inject(context.active(), headers);
  res.json({ http_headers: Object.entries(headers) });
});

// Additional Endpoints
app.post('/trace/span/start', (req, res) => {
  const args = req.body;
  let parent;
  if (args.parent_id) {
    parent = spans[args.parent_id];
  } else {
    parent = null;
  }

  if (args.origin !== '') {
    const traceId = parent ? parent.traceId : null;
    const parentId = parent ? parent.spanId : null;
    parent = new diag.Context({ traceId, spanId: parentId, dd_origin: args.origin });
  }

  if (args.http_headers.length > 0) {
    const headers = Object.fromEntries(args.http_headers);
    parent = HttpTraceContext.extract(headers);
  }

  const span = sdk.trace.startSpan(args.name, {
    childOf: parent,
    attributes: { service: args.service, type: args.type, resource: args.resource },
  });

  for (const link of args.links) {
    const linkParentId = link.parent_id;
    const linkAttributes = link.attributes;
    for (const [k, v] of Object.entries(linkAttributes)) {
      if (typeof v === 'string' && (v.startsWith('[') || v.startsWith('{'))) {
        linkAttributes[k] = eval(v);
      }
    }

    if (linkParentId !== 0) {
      const linkParent = spans[linkParentId];
      span.setSpanContext(linkParent.spanContext());
    } else {
      const ctx = HttpTraceContext.extract(headers);
      span.addLink({ context: ctx, attributes: linkAttributes });
    }
  }

  spans[span.spanId] = span;
  res.json({ span_id: span.spanId, trace_id: span.traceId });
});

app.post('/trace/span/finish', (req, res) => {
  const spanId = req.body.span_id;
  spans[spanId].end();
  res.json({});
});

app.post('/trace/span/set_meta', (req, res) => {
  const args = req.body;
  const spanId = args.span_id;
  const key = args.key;
  const value = args.value;
  spans[spanId].setTag(key, value);
  res.json({});
});

app.post('/trace/span/set_metric', (req, res) => {
  const args = req.body;
  const spanId = args.span_id;
  const key = args.key;
  const value = args.value;
  spans[spanId].setMetric(key, value);
  res.json({});
});

app.post('/trace/stats/flush', (req, res) => {
  sdk.trace.flush();
  res.json({});
});

app.post('/trace/span/error', (req, res) => {
  const args = req.body;
  const spanId = args.span_id;
  const type = args.type;
  const message = args.message;
  const stack = args.stack;
  spans[spanId].setTag(ERROR_MSG, message);
  spans[spanId].setTag(ERROR_TYPE, type);
  spans[spanId].setTag(ERROR_STACK, stack);
  spans[spanId].setTag('error', 1);
  res.json({});
});

app.post('/trace/otel/start_span', (req, res) => {
  const args = req.body;
  const otelTracer = trace.getTracer('otel-plugin');
  let parentSpan;
  if (args.parent_id) {
    parentSpan = otelSpans[args.parent_id];
  } else if (args.http_headers.length > 0) {
    const headers = Object.fromEntries(args.http_headers);
    const ddContext = HttpTraceContext.extract(headers);
    parentSpan = new OtelNonRecordingSpan({
      traceId: ddContext.traceId,
      spanId: ddContext.spanId,
      sampled: true,
      traceFlags: ddContext.samplingPriority && ddContext.samplingPriority > 0 ? TraceFlags.SAMPLED : TraceFlags.DEFAULT,
      traceState: TraceState.fromHeader(ddContext._tracestate),
    });
  } else {
    parentSpan = null;
  }

  const otelSpan = otelTracer.startSpan(args.name, {
    parent: parentSpan,
    kind: args.span_kind,
    attributes: args.attributes,
    links: null,
    startTime: args.timestamp * 1e3 || undefined,
    recordException: true,
    setStatusOnException: true,
  });

  const ctx = otelSpan.getSpanContext();
  otelSpans[ctx.spanId] = otelSpan;
  res.json({ span_id: ctx.spanId, trace_id: ctx.traceId });
});

app.post('/trace/otel/end_span', (req, res) => {
  const args = req.body;
  const span = otelSpans[args.id];
  const timestamp = args.timestamp;
  if (timestamp !== undefined) {
    span.end(timestamp * 1e3);
  } else {
    span.end();
  }
  res.json({});
});

app.post('/trace/otel/flush', (req, res) => {
  sdk.trace.flush();
  spans = {};
  otelSpans = {};
  res.json({ success: true });
});

app.post('/trace/otel/is_recording', (req, res) => {
  const args = req.body;
  const span = otelSpans[args.span_id];
  res.json({ is_recording: span.isRecording() });
});

app.post('/trace/otel/span_context', (req, res) => {
  const args = req.body;
  const span = otelSpans[args.span_id];
  const ctx = span.getSpanContext();
  res.json({
    span_id: ctx.spanId.toString(16).padStart(16, '0'),
    trace_id: ctx.traceId.toString(16).padStart(32, '0'),
    trace_flags: ctx.traceFlags.toString(16).padStart(2, '0'),
    trace_state: ctx.traceState.toHeader(),
    remote: ctx.isRemote,
  });
});

app.post('/trace/otel/set_status', (req, res) => {
  const args = req.body;
  const span = otelSpans[args.span_id];
  const statusCode = args.code.toUpperCase();
  const status = StatusCode[statusCode];
  const description = args.description;
  span.setStatus({ code: status, message: description });
  res.json({});
});

app.post('/trace/otel/set_name', (req, res) => {
  const args = req.body;
  const span = otelSpans[args.span_id];
  span.updateName(args.name);
  res.json({});
});

app.post('/trace/otel/set_attributes', (req, res) => {
  const args = req.body;
  const span = otelSpans[args.span_id];
  span.setAttributes(args.attributes);
  res.json({});
});

const port = 3000;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
