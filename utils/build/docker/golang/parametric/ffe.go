package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	of "github.com/open-feature/go-sdk/openfeature"
)

func (s *apmClientServer) ffeStart(http.ResponseWriter, *http.Request) {
	return
}

func (s *apmClientServer) ffeEval(writer http.ResponseWriter, request *http.Request) {
	var body struct {
		Flag          string         `json:"flag"`
		VariationType string         `json:"variationType"`
		DefaultValue  any            `json:"defaultValue"`
		TargetingKey  string         `json:"targetingKey"`
		Attributes    map[string]any `json:"attributes"`
		SpanID        string         `json:"span_id"`
	}
	if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
		http.Error(writer, "invalid request body: "+err.Error(), http.StatusBadRequest)
		return
	}

	// Build the request context, optionally activating the requested span so
	// that the tracer can attach span-enrichment tags to the correct span.
	reqCtx := request.Context()
	if body.SpanID != "" {
		if spanID, err := strconv.ParseUint(body.SpanID, 10, 64); err == nil {
			if span, ok := s.spans[spanID]; ok {
				reqCtx = tracer.ContextWithSpan(context.Background(), span)
			}
		}
	}

	ctx := of.NewEvaluationContext(body.TargetingKey, body.Attributes)

	if initer, ok := s.ddProvider.(of.StateHandler); ok {
		initer.Init(ctx)
	}

	val := s.ofClient.Object(reqCtx, body.Flag, body.DefaultValue, ctx)

	writer.WriteHeader(http.StatusOK)

	response := struct {
		Value any `json:"value"`
	}{val}

	if err := json.NewEncoder(writer).Encode(response); err != nil {
		http.Error(writer, "failed to encode response: "+err.Error(), http.StatusInternalServerError)
	}
}
