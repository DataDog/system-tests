package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"sync"
	"time"

	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
)

// ffeStartTimeout bounds the wait for the first configuration. Above the 10s
// DD_EXPERIMENTAL_FLAGGING_PROVIDER_INITIALIZATION_TIMEOUT_MS default, so the
// tracer's own timeout governs whenever it applies one.
const ffeStartTimeout = 15 * time.Second

var ffeStartOnce sync.Once

func (s *apmClientServer) ffeStart(writer http.ResponseWriter, request *http.Request) {
	var startErr error
	ffeStartOnce.Do(func() {
		provider, err := ddof.NewDatadogProvider(ddof.ProviderConfig{})
		if err != nil {
			startErr = err
			return
		}

		// Wait for Init: plain SetProvider returns before it, so /ffe/start would
		// answer 200 with no configuration and the next evaluation gets the
		// default. Other SDKs block on initialize inside set_provider.
		//
		// The deadline is ours rather than SetProviderAndWait's background
		// context, so tracers that only bound Init still cannot hang the suite.
		//
		// PROVIDER_NOT_READY is not a start failure: the provider is registered
		// and evaluations return defaults until configuration arrives.
		ctx, cancel := context.WithTimeout(context.Background(), ffeStartTimeout)
		defer cancel()

		if err := of.SetProviderWithContextAndWait(ctx, provider); err != nil {
			var initErr *of.ProviderInitError
			if !errors.As(err, &initErr) || initErr.ErrorCode != of.ProviderNotReadyCode {
				startErr = err
				return
			}
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
