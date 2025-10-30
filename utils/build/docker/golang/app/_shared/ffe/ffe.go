package ffe

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/open-feature/go-sdk/openfeature"
)

// EvaluateRequest represents the request body for flag evaluation
type EvaluateRequest struct {
	Flag          string                 `json:"flag"`
	VariationType string                 `json:"variationType"`
	DefaultValue  interface{}            `json:"defaultValue"`
	TargetingKey  string                 `json:"targetingKey"`
	Attributes    map[string]interface{} `json:"attributes"`
}

// EvaluateResponse represents the response body for flag evaluation
type EvaluateResponse struct {
	Value interface{} `json:"value"`
}

// client holds the OpenFeature client instance
var client *openfeature.Client

// InitHandler initializes the FFE provider (for weblog endpoints)
func InitHandler(w http.ResponseWriter, r *http.Request) {
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
	client = openfeature.NewClient("weblog")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{})
}

// EvaluateHandler evaluates a feature flag (for weblog endpoints)
func EvaluateHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req EvaluateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON body", http.StatusBadRequest)
		return
	}

	if client == nil {
		http.Error(w, "FFE provider not initialized", http.StatusInternalServerError)
		return
	}

	// Build evaluation context
	ctx := context.Background()
	evalCtx := openfeature.NewEvaluationContext(req.TargetingKey, req.Attributes)

	var value interface{}

	// Evaluate flag based on variation type
	switch req.VariationType {
	case "BOOLEAN":
		defaultBool, ok := req.DefaultValue.(bool)
		if !ok {
			http.Error(w, "Invalid default value for BOOLEAN type", http.StatusBadRequest)
			return
		}
		result := client.BooleanValue(ctx, req.Flag, defaultBool, evalCtx)
		value = result.Value

	case "STRING":
		defaultStr, ok := req.DefaultValue.(string)
		if !ok {
			http.Error(w, "Invalid default value for STRING type", http.StatusBadRequest)
			return
		}
		result := client.StringValue(ctx, req.Flag, defaultStr, evalCtx)
		value = result.Value

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
		result := client.FloatValue(ctx, req.Flag, defaultFloat, evalCtx)
		value = result.Value

	case "JSON":
		defaultObj, ok := req.DefaultValue.(map[string]interface{})
		if !ok {
			// Try to handle other object types
			defaultObj = map[string]interface{}{"value": req.DefaultValue}
		}
		result := client.ObjectValue(ctx, req.Flag, defaultObj, evalCtx)
		value = result.Value

	default:
		http.Error(w, fmt.Sprintf("Unknown variation type: %s", req.VariationType), http.StatusBadRequest)
		return
	}

	response := EvaluateResponse{
		Value: value,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}