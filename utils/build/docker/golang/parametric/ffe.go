package main

import (
	"encoding/json"
	"net/http"
	"sync"

	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
)

var ffeStartOnce sync.Once

func (s *apmClientServer) ffeStart(writer http.ResponseWriter, request *http.Request) {
	var startErr error
	ffeStartOnce.Do(func() {
		provider, err := ddof.NewDatadogProvider(ddof.ProviderConfig{})
		if err != nil {
			startErr = err
			return
		}

		if err := of.SetProvider(provider); err != nil {
			startErr = err
			return
		}

		s.ddProvider = provider
		s.ofClient = of.NewClient("system-tests-weblog-client")
	})

	if startErr != nil {
		writer.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(writer).Encode(map[string]string{"error": startErr.Error()})
		return
	}

	writer.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(writer).Encode(map[string]any{})
}

func (s *apmClientServer) ffeEval(writer http.ResponseWriter, request *http.Request) {
	var body struct {
		Flag          string         `json:"flag"`
		VariationType string         `json:"variationType"`
		DefaultValue  any            `json:"defaultValue"`
		TargetingKey  string         `json:"targetingKey"`
		Attributes    map[string]any `json:"attributes"`
	}
	if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
		http.Error(writer, "invalid request body: "+err.Error(), http.StatusBadRequest)
		return
	}

	if s.ofClient == nil {
		writer.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(writer).Encode(map[string]string{"error": "FFE provider not initialized"})
		return
	}

	switch body.VariationType {
	case "BOOLEAN", "STRING", "INTEGER", "NUMERIC", "JSON":
	default:
		http.Error(writer, "unknown variation type: "+body.VariationType, http.StatusBadRequest)
		return
	}

	ctx := of.NewEvaluationContext(body.TargetingKey, body.Attributes)

	value := body.DefaultValue
	reason := string(of.DefaultReason)
	var errorCode string

	evalCtx := request.Context()

	func() {
		defer func() {
			if r := recover(); r != nil {
				value = body.DefaultValue
				reason = "ERROR"
			}
		}()

		switch body.VariationType {
		case "BOOLEAN":
			defaultValue, _ := body.DefaultValue.(bool)
			details, err := s.ofClient.BooleanValueDetails(evalCtx, body.Flag, defaultValue, ctx)
			if err != nil {
				value = body.DefaultValue
				reason = "ERROR"
				return
			}
			value = details.Value
			reason = string(details.Reason)
			errorCode = string(details.ErrorCode)
		case "STRING":
			defaultValue, _ := body.DefaultValue.(string)
			details, err := s.ofClient.StringValueDetails(evalCtx, body.Flag, defaultValue, ctx)
			if err != nil {
				value = body.DefaultValue
				reason = "ERROR"
				return
			}
			value = details.Value
			reason = string(details.Reason)
			errorCode = string(details.ErrorCode)
		case "INTEGER":
			defaultValue, _ := toInt64(body.DefaultValue)
			details, err := s.ofClient.IntValueDetails(evalCtx, body.Flag, defaultValue, ctx)
			if err != nil {
				value = body.DefaultValue
				reason = "ERROR"
				return
			}
			value = details.Value
			reason = string(details.Reason)
			errorCode = string(details.ErrorCode)
		case "NUMERIC":
			defaultValue, _ := toFloat64(body.DefaultValue)
			details, err := s.ofClient.FloatValueDetails(evalCtx, body.Flag, defaultValue, ctx)
			if err != nil {
				value = body.DefaultValue
				reason = "ERROR"
				return
			}
			value = details.Value
			reason = string(details.Reason)
			errorCode = string(details.ErrorCode)
		case "JSON":
			details, err := s.ofClient.ObjectValueDetails(evalCtx, body.Flag, body.DefaultValue, ctx)
			if err != nil {
				value = body.DefaultValue
				reason = "ERROR"
				return
			}
			value = details.Value
			reason = string(details.Reason)
			errorCode = string(details.ErrorCode)
		}
	}()

	writer.WriteHeader(http.StatusOK)
	response := struct {
		Value     any    `json:"value"`
		Reason    string `json:"reason"`
		ErrorCode string `json:"errorCode"`
	}{value, reason, errorCode}

	if err := json.NewEncoder(writer).Encode(response); err != nil {
		http.Error(writer, "failed to encode response: "+err.Error(), http.StatusInternalServerError)
	}
}

func toInt64(v any) (int64, bool) {
	switch n := v.(type) {
	case int64:
		return n, true
	case int:
		return int64(n), true
	case float64:
		return int64(n), true
	default:
		return 0, false
	}
}

func toFloat64(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	default:
		return 0, false
	}
}
