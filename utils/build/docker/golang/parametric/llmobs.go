package main

// This file reorients the /llm_observability/trace endpoint from the native
// dd-trace-go llmobs SDK path to an OTel gen_ai OTLP path.
//
// Design (verified against the parametric app + OTLP capture research):
//   - We DO NOT add any new module. Spans are created through the app's EXISTING
//     ddotel bridge provider (s.tp, a *ddotel.TracerProvider created in
//     newServer()). dd-trace-go's own OTLP trace exporter — enabled by the
//     scenario via OTEL_TRACES_EXPORTER=otlp + OTEL_EXPORTER_OTLP_TRACES_* — ships
//     these spans as OTLP/JSON to the ddapm-test-agent OTLP receiver, exactly the
//     transport the hermetic test_otlp_trace_metrics.py tests already rely on
//     (see test_fr15_3, which reads /v1/traces off the OTLP receiver for spans
//     produced by dd-trace-go's OTLP export). No upstream otlptrace exporter and
//     no sdktrace provider is introduced, so this compiles against the deps
//     already in parametric/go.mod.
//   - The intake headers (dd-otlp-source=llmobs, dd-ml-app, dd-api-key) are set on
//     the exporter via OTEL_EXPORTER_OTLP_TRACES_HEADERS (scenario env), not in
//     code, because dd-trace-go's OTLP exporter reads standard OTLP env.
//   - Each SpanRequest node is mapped to gen_ai.* attributes per the authoritative
//     Datadog LLM Obs OTel schema. The backend mapping of those attributes is NOT
//     asserted here; the hermetic pytest only asserts the emitted OTLP payload's
//     gen_ai.* attributes + headers.
//
// The /llm_observability/trace input contract (the SpanRequest tree) is
// unchanged, so the harness can still drive it via test_library.llmobs_trace().
//
// TODO(draft): whether dd-trace-go's OTLP trace export preserves arbitrary
// gen_ai.* string attributes verbatim (vs. remapping/dropping them) is the key
// unverified assumption; the pytest is what proves or disproves it.

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"go.opentelemetry.io/otel/attribute"
	oteltrace "go.opentelemetry.io/otel/trace"
)

// ---------------------------------------------------------------------------
// Request types — unchanged from the native draft; they mirror the harness-side
// dataclasses in utils/docker_fixtures/spec/llm_observability.py. The three node
// shapes (ApmSpanRequest, LlmObsSpanRequest, LlmObsAnnotationContextRequest) fold
// into one recursive struct discriminated by "type"/"sdk".
// ---------------------------------------------------------------------------

type llmObsTraceRequest struct {
	TraceStructureRequest *llmObsSpanNode `json:"trace_structure_request"`
}

type llmObsSpanNode struct {
	Type string `json:"type"` // "span" (default) | "annotation_context"
	SDK  string `json:"sdk"`  // "tracer" | "llmobs"
	Name string `json:"name"`

	// LlmObsSpanRequest-only fields.
	Kind          string `json:"kind"`
	SessionID     string `json:"session_id"`
	MLApp         string `json:"ml_app"`
	ModelName     string `json:"model_name"`
	ModelProvider string `json:"model_provider"`

	Children      []*llmObsSpanNode         `json:"children"`
	Annotations   []llmObsAnnotationRequest `json:"annotations"`
	AnnotateAfter bool                      `json:"annotate_after"`
	ExportSpan    string                    `json:"export_span"` // "explicit" | "implicit"

	// LlmObsAnnotationContextRequest-only fields (also reuses Name/Children).
	Prompt   map[string]any `json:"prompt"`
	Tags     map[string]any `json:"tags"`
	CostTags []any          `json:"cost_tags"`
}

type llmObsAnnotationRequest struct {
	InputData    any                `json:"input_data"`
	OutputData   any                `json:"output_data"`
	Metadata     map[string]any     `json:"metadata"`
	Metrics      map[string]float64 `json:"metrics"`
	Tags         map[string]any     `json:"tags"`
	CostTags     []any              `json:"cost_tags"`
	Prompt       map[string]any     `json:"prompt"`
	ExplicitSpan bool               `json:"explicit_span"`
}

// ---------------------------------------------------------------------------
// POST /llm_observability/trace
// ---------------------------------------------------------------------------

func (s *apmClientServer) llmObsTraceHandler(w http.ResponseWriter, r *http.Request) {
	// dd-trace-go's OTLP trace exporter (scenario: OTEL_TRACES_EXPORTER=otlp +
	// OTEL_EXPORTER_OTLP_TRACES_*) is what ships these spans to the test-agent OTLP
	// receiver. tracer.Flush() pushes the trace writer; the hermetic test also
	// polls the OTLP receiver with a deadline as a backstop.
	//
	// TODO(draft): confirm tracer.Flush() drains the OTLP trace exporter and not
	// only the native trace writer. If it does not, an explicit OTLP exporter
	// flush hook (or a short poll on the receiver) is required.
	defer tracer.Flush()

	var req llmObsTraceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	tr := s.tp.Tracer("system-tests-llmobs")
	exported := s.buildGenAISpan(context.Background(), tr, req.TraceStructureRequest)
	if exported == nil {
		// Success with no export requested -> {} (mirrors llmobs.py llmobs_trace).
		exported = map[string]any{}
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(exported); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// buildGenAISpan walks the recursive SpanRequest tree, emitting one OTel span per
// node with gen_ai.* attributes, and bubbles up the first exported span context.
func (s *apmClientServer) buildGenAISpan(ctx context.Context, tr oteltrace.Tracer, node *llmObsSpanNode) map[string]any {
	if node == nil {
		return nil
	}

	// annotation_context has no gen_ai equivalent (it is a dd-trace-py scope that
	// applies prompt/name/tags to spans opened within the block). Recurse so the
	// tree/parentage is preserved; the contextual annotations are dropped.
	// TODO(draft): if the contract needs those tags on descendant spans, apply
	// node.Tags/node.Prompt to each child span here.
	if node.Type == "annotation_context" {
		var exported map[string]any
		for _, child := range node.Children {
			if e := s.buildGenAISpan(ctx, tr, child); e != nil && exported == nil {
				exported = e
			}
		}
		return exported
	}

	name := node.Name
	if name == "" {
		name = node.Kind
	}
	spanCtx, span := tr.Start(ctx, name)

	attrs := genAIBaseAttributes(node)
	for _, a := range node.Annotations {
		attrs = append(attrs, genAIAnnotationAttributes(node.Kind, a)...)
	}
	if len(attrs) > 0 {
		span.SetAttributes(attrs...)
	}

	var exported map[string]any
	if node.ExportSpan != "" {
		// The hermetic test does not read the export dict back from a backend, so
		// the OTel span/trace ids (hex) are a best-effort echo. Both "explicit" and
		// "implicit" resolve to the same span here.
		exported = map[string]any{
			"span_id":  span.SpanContext().SpanID().String(),
			"trace_id": span.SpanContext().TraceID().String(),
		}
		if node.MLApp != "" {
			exported["ml_app"] = node.MLApp
		}
	}

	for _, child := range node.Children {
		if e := s.buildGenAISpan(spanCtx, tr, child); e != nil && exported == nil {
			exported = e
		}
	}

	span.End()
	return exported
}

// genAIBaseAttributes maps the node's kind/model/session onto gen_ai.* attributes.
func genAIBaseAttributes(node *llmObsSpanNode) []attribute.KeyValue {
	if node.SDK == "tracer" {
		// Plain APM-style span: no gen_ai.* attributes, kept only for tree shape.
		// TODO(draft): gen_ai has no APM-span concept; such a node defaults to a
		// workflow span on the backend (operation.name omitted).
		return nil
	}

	var attrs []attribute.KeyValue
	if op, ok := genAIOperation(node.Kind); ok {
		attrs = append(attrs, attribute.String("gen_ai.operation.name", op))
	}
	if node.ModelName != "" {
		attrs = append(attrs, attribute.String("gen_ai.request.model", node.ModelName))
	}
	if node.ModelProvider != "" {
		attrs = append(attrs, attribute.String("gen_ai.provider.name", node.ModelProvider))
	}
	if node.SessionID != "" {
		attrs = append(attrs, attribute.String("gen_ai.conversation.id", node.SessionID))
	}
	return attrs
}

// genAIOperation maps a SpanRequest kind to gen_ai.operation.name per the schema:
// chat->llm, embeddings->embedding, execute_tool->tool, invoke_agent->agent;
// anything else (including workflow) defaults to a workflow span when the
// attribute is omitted.
func genAIOperation(kind string) (string, bool) {
	switch kind {
	case "llm":
		return "chat", true
	case "embedding":
		return "embeddings", true
	case "tool":
		return "execute_tool", true
	case "agent":
		return "invoke_agent", true
	case "workflow", "task", "retrieval", "":
		// default -> workflow. task/retrieval have no authoritative gen_ai operation.
		// TODO(draft): confirm task/retrieval are acceptable as workflow spans.
		return "", false
	default:
		return "", false
	}
}

// genAIAnnotationAttributes maps a single annotation onto gen_ai I/O + usage +
// metadata attributes. The same gen_ai.input.messages / gen_ai.output.messages
// attributes are used for every kind; the backend routes them to
// meta.input.messages (llm) or meta.input.value (others).
func genAIAnnotationAttributes(kind string, a llmObsAnnotationRequest) []attribute.KeyValue {
	var attrs []attribute.KeyValue
	if a.InputData != nil {
		attrs = append(attrs, attribute.String("gen_ai.input.messages", genAIMessagesJSON(a.InputData)))
	}
	if a.OutputData != nil {
		attrs = append(attrs, attribute.String("gen_ai.output.messages", genAIMessagesJSON(a.OutputData)))
	}
	if len(a.Metadata) > 0 {
		if b, err := json.Marshal(a.Metadata); err == nil {
			// Custom metadata is carried as a JSON string; the backend merges
			// _dd.ml_obs.metadata into meta.metadata.
			attrs = append(attrs, attribute.String("_dd.ml_obs.metadata", string(b)))
		}
	}
	attrs = append(attrs, genAIUsageAttributes(a.Metrics)...)

	// TODO(draft): tags, prompt, and cost_tags have no authoritative gen_ai.*
	// attribute in this schema and are dropped. If needed, tags could be folded
	// into _dd.ml_obs.metadata and prompt into gen_ai.request.* / a prompt attr.
	_ = a.Tags
	_ = a.Prompt
	_ = a.CostTags
	_ = kind
	return attrs
}

// genAIUsageAttributes maps recognized token metrics to gen_ai.usage.* integers.
func genAIUsageAttributes(metrics map[string]float64) []attribute.KeyValue {
	if len(metrics) == 0 {
		return nil
	}
	usageKeys := map[string]string{
		"input_tokens":      "gen_ai.usage.input_tokens",
		"output_tokens":     "gen_ai.usage.output_tokens",
		"prompt_tokens":     "gen_ai.usage.prompt_tokens",
		"completion_tokens": "gen_ai.usage.completion_tokens",
		"total_tokens":      "gen_ai.usage.total_tokens",
	}
	var attrs []attribute.KeyValue
	for k, v := range metrics {
		if attrKey, ok := usageKeys[k]; ok {
			attrs = append(attrs, attribute.Int64(attrKey, int64(v)))
		}
		// TODO(draft): non-token custom metrics have no gen_ai.usage.* mapping
		// and are dropped.
	}
	return attrs
}

// genAIMessagesJSON renders an input/output value as the JSON string expected by
// gen_ai.input.messages / gen_ai.output.messages.
func genAIMessagesJSON(v any) string {
	msgs := toGenAIMessages(v)
	b, err := json.Marshal(msgs)
	if err != nil {
		return "[]"
	}
	return string(b)
}

func toGenAIMessages(v any) []map[string]any {
	switch t := v.(type) {
	case nil:
		return nil
	case string:
		return []map[string]any{{"content": t}}
	case map[string]any:
		return []map[string]any{normalizeMessage(t)}
	case []any:
		out := make([]map[string]any, 0, len(t))
		for _, e := range t {
			switch el := e.(type) {
			case string:
				out = append(out, map[string]any{"content": el})
			case map[string]any:
				out = append(out, normalizeMessage(el))
			default:
				out = append(out, map[string]any{"content": toText(el)})
			}
		}
		return out
	default:
		return []map[string]any{{"content": toText(t)}}
	}
}

// normalizeMessage keeps role/content when present (the common gen_ai message
// shape); everything else is stringified into content.
// TODO(draft): the full gen_ai message schema (role enum, structured parts) is
// not modeled; role/content passthrough is the minimal faithful subset.
func normalizeMessage(m map[string]any) map[string]any {
	msg := map[string]any{}
	if role, ok := m["role"]; ok {
		msg["role"] = role
	}
	if content, ok := m["content"]; ok {
		msg["content"] = content
	} else {
		msg["content"] = toText(m)
	}
	return msg
}

// toText renders a value as a string: strings pass through, everything else is
// JSON-encoded.
func toText(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf("%v", v)
	}
	return string(b)
}
