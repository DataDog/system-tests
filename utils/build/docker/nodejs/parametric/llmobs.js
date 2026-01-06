const { llmobs } = require('dd-trace'); // should already be initialized globally by the parent server
const telemetry = require('dd-trace/packages/dd-trace/src/telemetry');

/**
 * Adds the LLM Observability routes to the app.
 * The routes are used to start and end LLM Observability spans.
 *
 * @param {import('express').Application} app - The Express application.
 */
function addRoutes (app) {
  app.post('/llm_observability/trace', async (req, res) => {
    const maybeExportedSpanCtx = await createTrace(req.body.trace_structure_request);
    telemetry.appClosing();

    res.json(maybeExportedSpanCtx ?? {});
  });

  app.post('/sdk/flush', async (req, res) => {
    llmobs.flush();
    telemetry.appClosing()
    res.json({});
  });
}

async function createTrace (traceStructure) {
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

  await makeTrace(...args, async (_span) => {
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
      if (!Array.isArray(child)) {
        await createTrace(child);
      } else {
        // process all of the array in parallel/async
        await Promise.all(child.map(createTrace));
      }
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

    const args = [];

    if (annotation.explicit_span || annotateAfter) {
      args.push(span);
    }

    args.push({ inputData, outputData, metadata, metrics, tags });

    llmobs.annotate(...args);
  }
}

module.exports = addRoutes;