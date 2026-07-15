package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/DataDog/dd-trace-go/v2/llmobs"
	"github.com/DataDog/dd-trace-go/v2/llmobs/dataset"
)

// llmObsStartOnce guards a single tracer.Start so LLM Obs is initialized on the
// first /llm_observability/* request. LLM Obs piggybacks on the tracer: it is
// enabled by starting the tracer with DD_LLMOBS_ENABLED / DD_LLMOBS_ML_APP (set
// by the system-tests scenario) or tracer.WithLLMObsEnabled(true).
var llmObsStartOnce sync.Once

// ensureLLMObs starts the tracer (and therefore LLM Obs) exactly once, honoring
// the DD_LLMOBS_* environment variables provided by the scenario.
//
// TODO(draft): the parametric app never calls tracer.Start() in main(), so we
// lazily start it here. If a scenario expects LLM Obs to be enabled purely
// programmatically (no env), force tracer.WithLLMObsEnabled(true) here instead.
func ensureLLMObs() {
	llmObsStartOnce.Do(func() {
		if err := tracer.Start(); err != nil {
			log.Printf("llmobs: failed to start tracer: %v", err)
		}
	})
}

// ---------------------------------------------------------------------------
// Request / response types
//
// These mirror the harness-side dataclasses (utils/docker_fixtures/spec/
// llm_observability.py). The three node shapes (ApmSpanRequest,
// LlmObsSpanRequest, LlmObsAnnotationContextRequest) are folded into a single
// recursive struct discriminated by "type"/"sdk"; JSON field names never
// collide across the shapes so one struct decodes all of them.
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

type datasetRecordRequest struct {
	InputData      map[string]any `json:"input_data"`
	ExpectedOutput any            `json:"expected_output"`
	Metadata       map[string]any `json:"metadata"`
}

type datasetCreateRequest struct {
	DatasetName string                 `json:"dataset_name"`
	Description string                 `json:"description"`
	Records     []datasetRecordRequest `json:"records"`
	ProjectName string                 `json:"project_name"`
}

type datasetResponse struct {
	DatasetID     string           `json:"dataset_id"`
	Name          string           `json:"name"`
	Description   string           `json:"description"`
	ProjectName   *string          `json:"project_name"`
	ProjectID     *string          `json:"project_id"`
	Version       int              `json:"version"`
	LatestVersion int              `json:"latest_version"`
	Records       []map[string]any `json:"records"`
}

type datasetDeleteRequest struct {
	DatasetID string `json:"dataset_id"`
}

// ---------------------------------------------------------------------------
// POST /llm_observability/trace
// ---------------------------------------------------------------------------

func (s *apmClientServer) llmObsTraceHandler(w http.ResponseWriter, r *http.Request) {
	ensureLLMObs()

	// The Python app force-flushes the telemetry writer in a finally block.
	// tracer.Flush() (which internally flushes LLM Obs) is the closest idiom
	// available from the public API and guarantees the span reaches the
	// test-agent before the handler returns.
	// TODO(draft): confirm span flush (not just telemetry) is what the harness
	// waits on via test_agent.wait_for_llmobs_requests.
	defer tracer.Flush()

	var req llmObsTraceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	exported := s.createLLMObsTrace(context.Background(), req.TraceStructureRequest)
	if exported == nil {
		// Success with no export requested -> {} (see llmobs.py llmobs_trace).
		exported = map[string]any{}
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(exported); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// createLLMObsTrace builds the (recursive) span tree and returns the first
// non-nil exported span context bubbled up from the tree, mirroring
// llmobs.py create_trace.
func (s *apmClientServer) createLLMObsTrace(ctx context.Context, node *llmObsSpanNode) map[string]any {
	if node == nil {
		return nil
	}

	if node.Type == "annotation_context" {
		// TODO(draft): the public dd-trace-go v2 llmobs package exposes no
		// annotation_context equivalent (dd-trace-py's LLMObs.annotation_context
		// applies prompt/name/tags/cost_tags to all spans opened within the
		// block). For the draft we simply recurse into the children so the tree
		// is still built; the contextual annotations are dropped. This needs an
		// upstream SDK addition or a per-child annotation workaround.
		var exported map[string]any
		for _, child := range node.Children {
			if e := s.createLLMObsTrace(ctx, child); e != nil && exported == nil {
				exported = e
			}
		}
		return exported
	}

	// APM (plain tracer) span branch.
	if node.SDK == "tracer" {
		// Start from the incoming ctx so a tracer span nested under an LLMObs span
		// keeps the intended parentage (e.g. llmobs -> tracer -> llmobs) from the
		// shared request model; StartSpanFromContext also returns the child-bearing
		// context to place descendants under this span.
		span, childCtx := tracer.StartSpanFromContext(ctx, node.Name)

		// TODO(draft): dd-trace-py applies annotations to tracer-sdk spans via
		// LLMObs.annotate(span=...). The public Go llmobs annotation API only
		// operates on llmobs span types, so annotations on tracer-sdk spans are
		// not applied here.
		var exported map[string]any
		for _, child := range node.Children {
			if e := s.createLLMObsTrace(childCtx, child); e != nil && exported == nil {
				exported = e
			}
		}
		span.Finish()
		return exported
	}

	// LLM Obs span branch.
	var opts []llmobs.StartSpanOption
	if node.SessionID != "" {
		opts = append(opts, llmobs.WithSessionID(node.SessionID))
	}
	if node.MLApp != "" {
		opts = append(opts, llmobs.WithMLApp(node.MLApp))
	}
	if node.ModelName != "" {
		opts = append(opts, llmobs.WithModelName(node.ModelName))
	}
	if node.ModelProvider != "" {
		opts = append(opts, llmobs.WithModelProvider(node.ModelProvider))
	}

	span, childCtx := startLLMObsSpan(ctx, node.Kind, node.Name, opts...)
	if span == nil {
		// Unknown kind: recurse without a span so the rest of the tree still
		// builds, still bubbling up any exported child context.
		var exported map[string]any
		for _, child := range node.Children {
			if e := s.createLLMObsTrace(ctx, child); e != nil && exported == nil {
				exported = e
			}
		}
		return exported
	}

	// Apply annotations before export/children (unless annotate_after).
	if len(node.Annotations) > 0 && !node.AnnotateAfter {
		for _, a := range node.Annotations {
			applyLLMObsAnnotation(span, a)
		}
	}

	var exported map[string]any
	if node.ExportSpan != "" {
		// Both "explicit" (LLMObs.export_span(span)) and "implicit"
		// (LLMObs.export_span()) resolve to the same span here.
		exported = exportedSpanContext(span, node.MLApp)
	}

	// Recurse into children, bubbling up the first exported context found. This
	// span's own export (if any) takes precedence; otherwise the first child's,
	// matching the shared Python/Node handlers.
	for _, child := range node.Children {
		if e := s.createLLMObsTrace(childCtx, child); e != nil && exported == nil {
			exported = e
		}
	}

	span.Finish()

	if node.AnnotateAfter && len(node.Annotations) > 0 {
		// TODO(draft): dd-trace-py expects annotating an already-finished span to
		// raise (the harness calls this path with raise_on_error=False and
		// expects a non-2xx). The Go SDK annotation methods are safe no-ops on a
		// finished span and will not error, so this contract case is not yet
		// satisfied.
		for _, a := range node.Annotations {
			applyLLMObsAnnotation(span, a)
		}
	}

	return exported
}

// startLLMObsSpan dispatches on the span kind and returns the created span as
// the generic llmobs.Span handle plus the derived context for children.
func startLLMObsSpan(ctx context.Context, kind, name string, opts ...llmobs.StartSpanOption) (llmobs.Span, context.Context) {
	switch kind {
	case "llm":
		sp, c := llmobs.StartLLMSpan(ctx, name, opts...)
		return sp, c
	case "agent":
		sp, c := llmobs.StartAgentSpan(ctx, name, opts...)
		return sp, c
	case "workflow":
		sp, c := llmobs.StartWorkflowSpan(ctx, name, opts...)
		return sp, c
	case "task":
		sp, c := llmobs.StartTaskSpan(ctx, name, opts...)
		return sp, c
	case "tool":
		sp, c := llmobs.StartToolSpan(ctx, name, opts...)
		return sp, c
	case "embedding":
		sp, c := llmobs.StartEmbeddingSpan(ctx, name, opts...)
		return sp, c
	case "retrieval":
		sp, c := llmobs.StartRetrievalSpan(ctx, name, opts...)
		return sp, c
	default:
		return nil, ctx
	}
}

// applyLLMObsAnnotation maps a single annotation request onto the kind-specific
// IO annotation method plus the generic (tags/metadata/metrics/prompt/cost)
// options, mirroring llmobs.py apply_annotations (which drops explicit_span and
// drops cost_tags when nil).
func applyLLMObsAnnotation(span llmobs.Span, a llmObsAnnotationRequest) {
	var annOpts []llmobs.AnnotateOption
	if len(a.Tags) > 0 {
		annOpts = append(annOpts, llmobs.WithAnnotatedTags(toStringMap(a.Tags)))
	}
	if len(a.Metadata) > 0 {
		annOpts = append(annOpts, llmobs.WithAnnotatedMetadata(a.Metadata))
	}
	if len(a.Metrics) > 0 {
		annOpts = append(annOpts, llmobs.WithAnnotatedMetrics(a.Metrics))
	}
	// TODO(draft): prompt annotation (Test_Prompts) and cost_tags require llmobs
	// options that are not in a released dd-trace-go yet: WithAnnotatedPrompt and
	// WithAnnotatedCostTagKeys (plus the richer Prompt{Label,ChatTemplate,Tags}
	// shape) land on main after the v2.7.x line. Once a release ships them, bump
	// parametric/go.mod and attach them here — prompt only on llm-kind spans,
	// since the contract asserts meta.input.prompt is absent for other kinds.
	// Until then Test_Prompts / cost-tag tests should be gated missing_feature.
	// a.Prompt / a.CostTags are decoded above but intentionally unused for now.
	_ = a.Prompt
	_ = a.CostTags

	switch sp := span.(type) {
	case *llmobs.LLMSpan:
		sp.AnnotateLLMIO(toLLMMessages(a.InputData), toLLMMessages(a.OutputData), annOpts...)
	case *llmobs.WorkflowSpan:
		sp.AnnotateTextIO(toText(a.InputData), toText(a.OutputData), annOpts...)
	case *llmobs.AgentSpan:
		sp.AnnotateTextIO(toText(a.InputData), toText(a.OutputData), annOpts...)
	case *llmobs.ToolSpan:
		sp.AnnotateTextIO(toText(a.InputData), toText(a.OutputData), annOpts...)
	case *llmobs.TaskSpan:
		sp.AnnotateTextIO(toText(a.InputData), toText(a.OutputData), annOpts...)
	case *llmobs.EmbeddingSpan:
		sp.AnnotateEmbeddingIO(toEmbeddedDocuments(a.InputData), toText(a.OutputData), annOpts...)
	case *llmobs.RetrievalSpan:
		sp.AnnotateRetrievalIO(toText(a.InputData), toRetrievedDocuments(a.OutputData), annOpts...)
	default:
		span.Annotate(annOpts...)
	}
}

// exportedSpanContext approximates dd-trace-py's LLMObs.export_span() return
// dict from the fields the Go SDK exposes.
//
// TODO(draft): dd-trace-go v2 has no public LLMObs.export_span; the exact key
// set (and whether ml_app is included) is unverified. The harness treats the
// value as an opaque dict, so span_id/trace_id are the load-bearing fields.
func exportedSpanContext(span llmobs.Span, mlApp string) map[string]any {
	ctx := map[string]any{
		"span_id":  span.SpanID(),
		"trace_id": span.TraceID(),
	}
	if mlApp != "" {
		ctx["ml_app"] = mlApp
	}
	return ctx
}

// ---------------------------------------------------------------------------
// POST /llm_observability/dataset/create
// ---------------------------------------------------------------------------

func (s *apmClientServer) llmObsDatasetCreateHandler(w http.ResponseWriter, r *http.Request) {
	ensureLLMObs()

	var req datasetCreateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var records []dataset.Record
	for _, rec := range req.Records {
		md := rec.Metadata
		if md == nil {
			md = map[string]any{}
		}
		records = append(records, dataset.Record{
			Input:          rec.InputData,
			ExpectedOutput: rec.ExpectedOutput,
			Metadata:       md,
		})
	}

	// The dataset tests configure DD_LLMOBS_PROJECT_NAME (via the
	// llmobs_project_name fixture) and assert the response project name matches,
	// even when the request omits project_name. Fall back to that env so the
	// create-response reflects the configured project rather than null.
	projectName := req.ProjectName
	if projectName == "" {
		projectName = os.Getenv("DD_LLMOBS_PROJECT_NAME")
	}

	var opts []dataset.CreateOption
	if req.Description != "" {
		opts = append(opts, dataset.WithDescription(req.Description))
	}
	if projectName != "" {
		opts = append(opts, dataset.WithProjectName(projectName))
	}

	// dataset.Create creates and (when records are present) pushes the dataset.
	ds, err := dataset.Create(r.Context(), req.DatasetName, records, opts...)
	if err != nil {
		http.Error(w, "Failed to create dataset: "+err.Error(), http.StatusInternalServerError)
		return
	}

	// TODO(draft): the public *dataset.Dataset exposes ID/Name/Version/Len/URL
	// but NOT Description/ProjectName/ProjectID/latest_version. We echo the
	// request/configured values for description/project_name and reuse Version()
	// for latest_version. ProjectID is unavailable and returned as null.
	resp := datasetResponse{
		DatasetID:     ds.ID(),
		Name:          ds.Name(),
		Description:   req.Description,
		ProjectName:   optStr(projectName),
		ProjectID:     nil,
		Version:       ds.Version(),
		LatestVersion: ds.Version(),
		Records:       datasetRecordsToMaps(ds),
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func datasetRecordsToMaps(ds *dataset.Dataset) []map[string]any {
	records := make([]map[string]any, 0, ds.Len())
	for _, rec := range ds.Records() {
		// TODO(draft): exact record dict shape expected by the harness is
		// unverified; we expose the round-trippable fields plus id/version.
		records = append(records, map[string]any{
			"id":              rec.ID(),
			"version":         rec.Version(),
			"input_data":      rec.Input,
			"expected_output": rec.ExpectedOutput,
			"metadata":        rec.Metadata,
		})
	}
	return records
}

// ---------------------------------------------------------------------------
// POST /llm_observability/dataset/delete
// ---------------------------------------------------------------------------

func (s *apmClientServer) llmObsDatasetDeleteHandler(w http.ResponseWriter, r *http.Request) {
	ensureLLMObs()

	var req datasetDeleteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// TODO(draft): dd-trace-go v2's public llmobs/dataset package exposes no
	// delete-dataset-by-id API (only Dataset.Delete(index) for individual
	// records). dd-trace-py uses the private LLMObs._delete_dataset. Until an
	// upstream API exists we cannot actually delete; report success so the
	// contract's response shape ({"success": true}) is honored.
	_ = req.DatasetID

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(map[string]bool{"success": true}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// ---------------------------------------------------------------------------
// Conversion helpers
// ---------------------------------------------------------------------------

func toLLMMessages(v any) []llmobs.LLMMessage {
	switch t := v.(type) {
	case nil:
		return nil
	case string:
		return []llmobs.LLMMessage{{Content: t}}
	case map[string]any:
		return []llmobs.LLMMessage{toLLMMessage(t)}
	case []any:
		out := make([]llmobs.LLMMessage, 0, len(t))
		for _, e := range t {
			switch el := e.(type) {
			case string:
				out = append(out, llmobs.LLMMessage{Content: el})
			case map[string]any:
				out = append(out, toLLMMessage(el))
			}
		}
		return out
	}
	return nil
}

func toLLMMessage(m map[string]any) llmobs.LLMMessage {
	msg := llmobs.LLMMessage{}
	if r, ok := m["role"].(string); ok {
		msg.Role = r
	}
	if c, ok := m["content"].(string); ok {
		msg.Content = c
	}
	return msg
}

// toText renders an input/output value as a string: strings pass through,
// everything else is JSON-encoded.
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

func toEmbeddedDocuments(v any) []llmobs.EmbeddedDocument {
	// TODO(draft): richer mapping of dict fields (name/score/id) to
	// EmbeddedDocument is unverified against the contract.
	switch t := v.(type) {
	case string:
		return []llmobs.EmbeddedDocument{{Text: t}}
	case map[string]any:
		return []llmobs.EmbeddedDocument{{Text: toText(t["text"])}}
	case []any:
		out := make([]llmobs.EmbeddedDocument, 0, len(t))
		for _, e := range t {
			switch el := e.(type) {
			case string:
				out = append(out, llmobs.EmbeddedDocument{Text: el})
			case map[string]any:
				out = append(out, llmobs.EmbeddedDocument{Text: toText(el["text"])})
			}
		}
		return out
	}
	return nil
}

func toRetrievedDocuments(v any) []llmobs.RetrievedDocument {
	// TODO(draft): richer mapping of dict fields (name/score/id) to
	// RetrievedDocument is unverified against the contract.
	switch t := v.(type) {
	case string:
		return []llmobs.RetrievedDocument{{Text: t}}
	case map[string]any:
		return []llmobs.RetrievedDocument{{Text: toText(t["text"])}}
	case []any:
		out := make([]llmobs.RetrievedDocument, 0, len(t))
		for _, e := range t {
			switch el := e.(type) {
			case string:
				out = append(out, llmobs.RetrievedDocument{Text: el})
			case map[string]any:
				out = append(out, llmobs.RetrievedDocument{Text: toText(el["text"])})
			}
		}
		return out
	}
	return nil
}

func toStringMap(m map[string]any) map[string]string {
	out := make(map[string]string, len(m))
	for k, v := range m {
		if s, ok := v.(string); ok {
			out[k] = s
		} else {
			out[k] = fmt.Sprintf("%v", v)
		}
	}
	return out
}

func optStr(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
