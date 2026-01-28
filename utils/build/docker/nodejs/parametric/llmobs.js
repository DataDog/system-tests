const tracer = require('dd-trace'); // should already be initialized globally by the parent server
const { llmobs } = tracer;
const telemetry = require('dd-trace/packages/dd-trace/src/telemetry');

/**
 * Adds the LLM Observability routes to the app.
 * The routes are used to start and end LLM Observability spans.
 *
 * @param {import('express').Application} app - The Express application.
 */
function addRoutes (app) {
  app.post('/llm_observability/trace', (req, res) => {
    try {
      const maybeExportedSpanCtx = createTrace(req.body.trace_structure_request);
      res.json(maybeExportedSpanCtx ?? {});
    } finally {
      telemetry.appClosing();
    }
  });

  app.post('/llm_observability/submit_evaluation', (req, res) => {
    const { trace_id, span_id, label, metric_type, value, tags, ml_app, timestamp_ms } = req.body;
    const spanContext = {
      traceId: trace_id,
      spanId: span_id,
    }

    llmobs.submitEvaluation(spanContext, {
      label,
      metricType: metric_type,
      value,
      tags,
      mlApp: ml_app,
      timestampMs: timestamp_ms,
    })

    res.json({});
  })

  app.post('/sdk/flush', async (req, res) => {
    llmobs.flush();
    telemetry.appClosing()
    res.json({});
  });
}

function createTrace (traceStructure) {
  const type = traceStructure.type;
  if (type === 'annotation_context') {
    const { prompt, name, tags, children } = traceStructure;
    const options = {};
    if (prompt) options.prompt = normalizePromptArgument(prompt);
    if (name) options.name = name;
    if (tags) options.tags = tags;
    return llmobs.annotationContext(options, () => {
      let exportedSpanCtx;
      if (!Array.isArray(children)) return;

      for (const child of children) {
        const maybeExportedSpanCtx = createTrace(child);
        if (maybeExportedSpanCtx && !exportedSpanCtx) {
          exportedSpanCtx = maybeExportedSpanCtx;
        }
      }

      return exportedSpanCtx;
    });
  }


  const isLlmObs = traceStructure.sdk === 'llmobs';
  const makeTrace = traceStructure.sdk === 'llmobs' ? llmobs.trace.bind(llmobs) : tracer.trace.bind(tracer);

  let args;
  if (isLlmObs) {
    const options = { kind: traceStructure.kind, name: traceStructure.name };
    if (traceStructure.session_id) options.sessionId = traceStructure.session_id;
    if (traceStructure.ml_app) options.mlApp = traceStructure.ml_app;
    if (traceStructure.model_name) options.modelName = traceStructure.model_name;
    if (traceStructure.model_provider) options.modelProvider = traceStructure.model_provider;
    args = [options];
  } else {
    args = [traceStructure.name];
  }

  let exportedSpanCtx;

  const annotations = traceStructure.annotations;
  const annotateAfter = traceStructure.annotate_after;
  let span;

  makeTrace(...args, (_span) => {
    span = _span;

    // apply annotations
    if (annotations && !annotateAfter) {
      applyAnnotations(span, annotations);
    }

    // apply export span
    const exportSpan = traceStructure.export_span;
    if (exportSpan) {
      const args = exportSpan === 'explicit' ? [span] : [];
      exportedSpanCtx = llmobs.exportSpan(...args);
    }

    // trace children
    const children = traceStructure.children;
    if (!children) return;

    for (const child of children) {
      createTrace(child);
    }
  })

  if (annotateAfter) {
    // this case should always throw
    applyAnnotations(span, annotations, true);
  }

  return exportedSpanCtx;
}

function applyAnnotations (span, annotations, annotateAfter = false) {
  for (const annotation of annotations) {
    const inputData = annotation.input_data;
    const outputData = annotation.output_data;
    const metadata = annotation.metadata;
    const metrics = annotation.metrics;
    const tags = annotation.tags;
    const prompt = normalizePromptArgument(annotation.prompt);

    const args = [];

    if (annotation.explicit_span || annotateAfter) {
      args.push(span);
    }

    args.push({ inputData, outputData, metadata, metrics, tags, prompt });

    llmobs.annotate(...args);
  }
}

function normalizePromptArgument (prompt) {
  if (!prompt || typeof prompt === 'string') return prompt;

  const normalizedPrompt = {};
  if (prompt.version) normalizedPrompt.version = prompt.version;
  if (prompt.id) normalizedPrompt.id = prompt.id;
  if (prompt.variables) normalizedPrompt.variables = prompt.variables;
  if (prompt.tags) normalizedPrompt.tags = prompt.tags;
  if (prompt.rag_query_variables) normalizedPrompt.queryVariables = prompt.rag_query_variables;
  if (prompt.rag_context_variables) normalizedPrompt.contextVariables = prompt.rag_context_variables;

  // set template
  normalizedPrompt.template = prompt.template || prompt.chat_template;

  return normalizedPrompt;
}

module.exports = addRoutes;