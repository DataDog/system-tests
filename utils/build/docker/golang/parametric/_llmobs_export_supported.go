package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	llmobsexport "github.com/DataDog/dd-trace-go/v2/llmobs/export"
)

// The endpoint DTOs below mirror the LlmObsExport* parametric protocol in
// utils/docker_fixtures/spec/llm_observability.py. They map into these public
// dd-trace-go types introduced by DataDog/dd-trace-go#4936:
//   - client and submission options: llmobs/export/client.go
//   - SpanEvent, SpanLink, and ErrorMessage: llmobs/export/span.go
//   - EvaluationMetric: llmobs/export/eval_metric.go
//   - Result: llmobs/export/result.go
//
// Pinned upstream source root:
// https://github.com/DataDog/dd-trace-go/tree/81a6224f9794276d093e92c4e1f29af06ef4bff0
// SpanEvent, SpanLink, and ErrorMessage alias the canonical wire types in
// internal/llmobs/transport/span.go; EvaluationMetric aliases EvaluationConfig
// from internal/llmobs/evaluation.go.
type llmObsExportRequest struct {
	MLApp       string                          `json:"ml_app"`
	Service     string                          `json:"service"`
	Env         string                          `json:"env"`
	Version     string                          `json:"version"`
	CallService string                          `json:"call_service"`
	CallMLApp   string                          `json:"call_ml_app"`
	Spans       []llmObsExportSpanRequest       `json:"spans"`
	Evaluations []llmObsExportEvaluationRequest `json:"evaluations"`
}

type llmObsExportSpanRequest struct {
	TraceID       string                        `json:"trace_id"`
	SpanID        string                        `json:"span_id"`
	ParentID      string                        `json:"parent_id"`
	SessionID     string                        `json:"session_id"`
	Name          string                        `json:"name"`
	Service       string                        `json:"service"`
	Kind          string                        `json:"kind"`
	StartNS       int64                         `json:"start_ns"`
	DurationNS    int64                         `json:"duration_ns"`
	ModelName     string                        `json:"model_name"`
	ModelProvider string                        `json:"model_provider"`
	Input         string                        `json:"input"`
	Output        string                        `json:"output"`
	Metadata      map[string]any                `json:"metadata"`
	Metrics       map[string]float64            `json:"metrics"`
	Tags          []string                      `json:"tags"`
	SpanLinks     []llmObsExportSpanLinkRequest `json:"span_links"`
	APMTraceID    string                        `json:"apm_trace_id"`
	Error         *llmObsExportErrorRequest     `json:"error"`
}

type llmObsExportSpanLinkRequest struct {
	TraceID     string            `json:"trace_id"`
	TraceIDHigh uint64            `json:"trace_id_high"`
	SpanID      string            `json:"span_id"`
	Attributes  map[string]string `json:"attributes"`
	Tracestate  string            `json:"tracestate"`
	Flags       uint32            `json:"flags"`
}

type llmObsExportErrorRequest struct {
	Type    string `json:"type"`
	Message string `json:"message"`
	Stack   string `json:"stack"`
}

type llmObsExportEvaluationRequest struct {
	SpanID           string         `json:"span_id"`
	TraceID          string         `json:"trace_id"`
	TagKey           string         `json:"tag_key"`
	TagValue         string         `json:"tag_value"`
	Label            string         `json:"label"`
	MetricType       string         `json:"metric_type"`
	CategoricalValue *string        `json:"categorical_value"`
	ScoreValue       *float64       `json:"score_value"`
	BooleanValue     *bool          `json:"boolean_value"`
	JSONValue        map[string]any `json:"json_value"`
	Tags             []string       `json:"tags"`
	MLApp            string         `json:"ml_app"`
	TimestampMS      int64          `json:"timestamp_ms"`
	Assessment       string         `json:"assessment"`
	Reasoning        string         `json:"reasoning"`
	Metadata         map[string]any `json:"metadata"`
}

type llmObsExportResponse struct {
	Spans       llmObsExportResult `json:"spans"`
	Evaluations llmObsExportResult `json:"evaluations"`
}

type llmObsExportResult struct {
	Sent    int `json:"sent"`
	Dropped int `json:"dropped"`
	Failed  int `json:"failed"`
}

func init() {
	llmObsExportHandlerImpl = submitLlmObsExport
}

func submitLlmObsExport(s *apmClientServer, w http.ResponseWriter, r *http.Request) {
	var req llmObsExportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	client, err := llmobsexport.NewClient(
		req.MLApp,
		llmobsexport.WithAgentURL(os.Getenv("DD_TRACE_AGENT_URL")),
		llmobsexport.WithService(req.Service),
		llmobsexport.WithEnv(req.Env),
		llmobsexport.WithVersion(req.Version),
	)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	response := llmObsExportResponse{}
	if len(req.Spans) > 0 {
		result, submitErr := client.SubmitSpans(r.Context(), exportSpans(req.Spans), spanSubmitOptions(req)...)
		if submitErr != nil {
			http.Error(w, submitErr.Error(), http.StatusBadGateway)
			return
		}
		response.Spans = exportResult(result)
	}
	if len(req.Evaluations) > 0 {
		result, submitErr := client.SubmitEvaluations(
			r.Context(),
			exportEvaluations(req.Evaluations),
			evaluationSubmitOptions(req)...,
		)
		if submitErr != nil {
			http.Error(w, submitErr.Error(), http.StatusBadGateway)
			return
		}
		response.Evaluations = exportResult(result)
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func exportSpans(requests []llmObsExportSpanRequest) []llmobsexport.SpanEvent {
	events := make([]llmobsexport.SpanEvent, 0, len(requests))
	for _, req := range requests {
		options := []llmobsexport.SpanEventOption{
			llmobsexport.WithTiming(time.Unix(0, req.StartNS), time.Duration(req.DurationNS)),
			llmobsexport.WithModel(req.ModelName, req.ModelProvider),
			llmobsexport.WithTextIO(req.Input, req.Output),
			llmobsexport.WithMetadata(req.Metadata),
		}
		if req.Error != nil {
			options = append(options, llmobsexport.WithSpanError(llmobsexport.ErrorMessage{
				Type: req.Error.Type, Message: req.Error.Message, Stack: req.Error.Stack,
			}))
		}
		event := llmobsexport.NewSpanEvent(req.TraceID, req.SpanID, llmobsexport.Kind(req.Kind), options...)
		event.ParentID = req.ParentID
		event.SessionID = req.SessionID
		event.Name = req.Name
		event.Service = req.Service
		event.Tags = req.Tags
		event.Metrics = req.Metrics
		event.SpanLinks = exportSpanLinks(req.SpanLinks)
		event.DDAttributes.APMTraceID = req.APMTraceID
		events = append(events, event)
	}
	return events
}

func exportSpanLinks(requests []llmObsExportSpanLinkRequest) []llmobsexport.SpanLink {
	links := make([]llmobsexport.SpanLink, 0, len(requests))
	for _, req := range requests {
		links = append(links, llmobsexport.SpanLink{
			TraceID:     req.TraceID,
			TraceIDHigh: req.TraceIDHigh,
			SpanID:      req.SpanID,
			Attributes:  req.Attributes,
			Tracestate:  req.Tracestate,
			Flags:       req.Flags,
		})
	}
	return links
}

func exportEvaluations(requests []llmObsExportEvaluationRequest) []llmobsexport.EvaluationMetric {
	evaluations := make([]llmobsexport.EvaluationMetric, 0, len(requests))
	for _, req := range requests {
		evaluations = append(evaluations, llmobsexport.EvaluationMetric{
			SpanID:           req.SpanID,
			TraceID:          req.TraceID,
			TagKey:           req.TagKey,
			TagValue:         req.TagValue,
			Label:            req.Label,
			MetricType:       llmobsexport.MetricType(req.MetricType),
			CategoricalValue: req.CategoricalValue,
			ScoreValue:       req.ScoreValue,
			BooleanValue:     req.BooleanValue,
			JSONValue:        req.JSONValue,
			Tags:             req.Tags,
			MLApp:            req.MLApp,
			TimestampMS:      req.TimestampMS,
			Assessment:       req.Assessment,
			Reasoning:        req.Reasoning,
			Metadata:         req.Metadata,
		})
	}
	return evaluations
}

func spanSubmitOptions(req llmObsExportRequest) []llmobsexport.SubmitSpansOption {
	if req.CallService == "" {
		return nil
	}
	return []llmobsexport.SubmitSpansOption{llmobsexport.WithCallService(req.CallService)}
}

func evaluationSubmitOptions(req llmObsExportRequest) []llmobsexport.SubmitEvaluationsOption {
	if req.CallMLApp == "" {
		return nil
	}
	return []llmobsexport.SubmitEvaluationsOption{llmobsexport.WithCallMLApp(req.CallMLApp)}
}

func exportResult(result *llmobsexport.Result) llmObsExportResult {
	return llmObsExportResult{Sent: result.Sent, Dropped: result.Dropped, Failed: result.Failed}
}
