package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/open-feature/go-sdk/openfeature"
)

// FFEEvaluateRequest represents the request body for flag evaluation
type FFEEvaluateRequest struct {
	Flag          string                 `json:"flag"`
	VariationType string                 `json:"variationType"`
	DefaultValue  interface{}            `json:"defaultValue"`
	TargetingKey  string                 `json:"targetingKey"`
	Attributes    map[string]interface{} `json:"attributes"`
}

// FFEEvaluateResponse represents the response body for flag evaluation
type FFEEvaluateResponse struct {
	Value  interface{} `json:"value"`
	Reason string      `json:"reason"`
}

// ffeClient holds the OpenFeature client instance
var ffeClient *openfeature.Client

// ffeStartHandler initializes the FFE provider
func (s *apmClientServer) ffeStartHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Initialize the OpenFeature provider from dd-trace-go
	// This will use the dd-trace-go FFE provider when available in v2.4.0
	// The provider will be obtained from the tracer similar to Node.js: tracer.OpenFeatureProvider()

	// For now, we create a basic client - this will be replaced with:
	// provider := tracer.OpenFeatureProvider()
	// openfeature.SetProvider(provider)
	ffeClient = openfeature.NewClient("system-tests")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{})
}

// ffeEvaluateHandler evaluates a feature flag
func (s *apmClientServer) ffeEvaluateHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req FFEEvaluateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON body", http.StatusBadRequest)
		return
	}

	if ffeClient == nil {
		http.Error(w, "FFE provider not initialized", http.StatusInternalServerError)
		return
	}

	// Build evaluation context
	ctx := context.Background()
	evalCtx := openfeature.NewEvaluationContext(req.TargetingKey, req.Attributes)

	var value interface{}
	var reason string = "DEFAULT"

	// Evaluate flag based on variation type
	switch req.VariationType {
	case "BOOLEAN":
		defaultBool, ok := req.DefaultValue.(bool)
		if !ok {
			http.Error(w, "Invalid default value for BOOLEAN type", http.StatusBadRequest)
			return
		}
		result := ffeClient.BooleanValue(ctx, req.Flag, defaultBool, evalCtx)
		value = result.Value
		reason = string(result.Reason)

	case "STRING":
		defaultStr, ok := req.DefaultValue.(string)
		if !ok {
			http.Error(w, "Invalid default value for STRING type", http.StatusBadRequest)
			return
		}
		result := ffeClient.StringValue(ctx, req.Flag, defaultStr, evalCtx)
		value = result.Value
		reason = string(result.Reason)

	case "INTEGER", "NUMERIC":
		var defaultFloat float64
		switch v := req.DefaultValue.(type) {
		case float64:
			defaultFloat = v
		case int:
			defaultFloat = float64(v)
		case int64:
			defaultFloat = float64(v)
		default:
			http.Error(w, fmt.Sprintf("Invalid default value for %s type", req.VariationType), http.StatusBadRequest)
			return
		}
		result := ffeClient.FloatValue(ctx, req.Flag, defaultFloat, evalCtx)
		value = result.Value
		reason = string(result.Reason)

	case "JSON":
		defaultObj, ok := req.DefaultValue.(map[string]interface{})
		if !ok {
			// Try to handle other object types
			defaultObj = map[string]interface{}{"value": req.DefaultValue}
		}
		result := ffeClient.ObjectValue(ctx, req.Flag, defaultObj, evalCtx)
		value = result.Value
		reason = string(result.Reason)

	default:
		http.Error(w, fmt.Sprintf("Unknown variation type: %s", req.VariationType), http.StatusBadRequest)
		return
	}

	response := FFEEvaluateResponse{
		Value:  value,
		Reason: reason,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}