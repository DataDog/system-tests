package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"go.opentelemetry.io/otel/attribute"
	oteltrace "go.opentelemetry.io/otel/trace"
)

type llmObsTraceRequest struct {
	TraceStructureRequest *llmObsSpanNode `json:"trace_structure_request"`
}

type llmObsSpanNode struct {
	Type string `json:"type"`
	SDK  string `json:"sdk"`
	Name string `json:"name"`

	Kind          string `json:"kind"`
	SessionID     string `json:"session_id"`
	MLApp         string `json:"ml_app"`
	ModelName     string `json:"model_name"`
	ModelProvider string `json:"model_provider"`

	Children      []*llmObsSpanNode         `json:"children"`
	Annotations   []llmObsAnnotationRequest `json:"annotations"`
	AnnotateAfter bool                      `json:"annotate_after"`
	ExportSpan    string                    `json:"export_span"`

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

func (s *apmClientServer) llmObsTraceHandler(w http.ResponseWriter, r *http.Request) {
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
		exported = map[string]any{}
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(exported); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *apmClientServer) buildGenAISpan(ctx context.Context, tr oteltrace.Tracer, node *llmObsSpanNode) map[string]any {
	if node == nil {
		return nil
	}

	// gen_ai has no annotation-context equivalent, so preserve nesting while dropping its annotations.
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
		// Both export modes return the current OTel span context.
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

func genAIBaseAttributes(node *llmObsSpanNode) []attribute.KeyValue {
	if node.SDK == "tracer" {
		// Tracer nodes preserve tree shape but carry no gen_ai attributes.
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
		// These kinds have no authoritative gen_ai operation mapping.
		return "", false
	default:
		return "", false
	}
}

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
			// The backend merges this JSON string into meta.metadata.
			attrs = append(attrs, attribute.String("_dd.ml_obs.metadata", string(b)))
		}
	}
	attrs = append(attrs, genAIUsageAttributes(a.Metrics)...)

	// These fields have no authoritative gen_ai attribute mapping.
	_ = a.Tags
	_ = a.Prompt
	_ = a.CostTags
	_ = kind
	return attrs
}

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
	// Non-token metrics have no gen_ai usage mapping.
	for k, v := range metrics {
		if attrKey, ok := usageKeys[k]; ok {
			attrs = append(attrs, attribute.Int64(attrKey, int64(v)))
		}
	}
	return attrs
}

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

// Preserve the common role/content subset and encode other shapes as content.
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
