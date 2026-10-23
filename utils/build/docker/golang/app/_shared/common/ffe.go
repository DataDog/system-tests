package common

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"

	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
)

func FFeEval() func(writer http.ResponseWriter, request *http.Request) {
	ofClient := of.NewClient("system-tests-weblog-client")
	var providerMutex sync.Mutex
	providerInitialized := false

	initializeProvider := func() error {
		providerMutex.Lock()
		defer providerMutex.Unlock()

		if providerInitialized {
			return nil
		}

		ddProvider, err := ddof.NewDatadogProvider(ddof.ProviderConfig{})
		if err != nil {
			return fmt.Errorf("create Datadog OpenFeature provider: %w", err)
		}

		if err := of.SetProvider(ddProvider); err != nil {
			return fmt.Errorf("set Datadog OpenFeature provider: %w", err)
		}

		providerInitialized = true
		return nil
	}

	// Subscribe eagerly so Agent-backed scenarios can deliver Remote Config before their first evaluation.
	// FFE is optional in this shared weblog, so an unavailable provider must not prevent the app from starting.
	if err := initializeProvider(); err != nil {
		log.Printf("failed to initialize Datadog OpenFeature provider; will retry on request: %v", err)
	}

	return func(writer http.ResponseWriter, request *http.Request) {
		var body struct {
			Flag          string         `json:"flag"`
			VariationType string         `json:"variationType"`
			DefaultValue  any            `json:"defaultValue"`
			TargetingKey  string         `json:"targetingKey"`
			TargetingKeys []string       `json:"targetingKeys"`
			Attributes    map[string]any `json:"attributes"`
		}
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			http.Error(writer, "invalid request body", http.StatusBadRequest)
			return
		}

		// Retry after a startup failure so temporarily unavailable providers can recover.
		if err := initializeProvider(); err != nil {
			log.Printf("failed to initialize Datadog OpenFeature provider: %v", err)
			http.Error(writer, "Datadog OpenFeature provider unavailable", http.StatusServiceUnavailable)
			return
		}

		ctx := request.Context()
		targetingKeys := body.TargetingKeys
		if len(targetingKeys) == 0 {
			targetingKeys = []string{body.TargetingKey}
		}

		var val any
		var details of.EvaluationDetails
		for _, targetingKey := range targetingKeys {
			evalCtx := of.NewEvaluationContext(targetingKey, body.Attributes)
			switch body.VariationType {
			case "BOOLEAN":
				defBool, _ := body.DefaultValue.(bool)
				result, _ := ofClient.BooleanValueDetails(ctx, body.Flag, defBool, evalCtx)
				val, details = result.Value, result.EvaluationDetails
			case "STRING":
				defStr, _ := body.DefaultValue.(string)
				result, _ := ofClient.StringValueDetails(ctx, body.Flag, defStr, evalCtx)
				val, details = result.Value, result.EvaluationDetails
			case "INTEGER":
				defFloat, _ := body.DefaultValue.(float64)
				result, _ := ofClient.IntValueDetails(ctx, body.Flag, int64(defFloat), evalCtx)
				val, details = result.Value, result.EvaluationDetails
			case "NUMERIC":
				defFloat, _ := body.DefaultValue.(float64)
				result, _ := ofClient.FloatValueDetails(ctx, body.Flag, defFloat, evalCtx)
				val, details = result.Value, result.EvaluationDetails
			default:
				result, _ := ofClient.ObjectValueDetails(ctx, body.Flag, body.DefaultValue, evalCtx)
				val, details = result.Value, result.EvaluationDetails
			}
		}

		writer.WriteHeader(http.StatusOK)

		metadata := details.FlagMetadata
		if metadata == nil {
			metadata = of.FlagMetadata{}
		}
		allocationKey, _ := metadata["dd.allocation.key"].(string)
		response := struct {
			Value         any             `json:"value"`
			Count         int             `json:"count"`
			Reason        of.Reason       `json:"reason"`
			ErrorCode     of.ErrorCode    `json:"errorCode"`
			Variant       string          `json:"variant"`
			FlagMetadata  of.FlagMetadata `json:"flagMetadata"`
			AllocationKey string          `json:"allocationKey,omitempty"`
		}{
			Value:         val,
			Count:         len(targetingKeys),
			Reason:        details.Reason,
			ErrorCode:     details.ErrorCode,
			Variant:       details.Variant,
			FlagMetadata:  metadata,
			AllocationKey: allocationKey,
		}

		if err := json.NewEncoder(writer).Encode(response); err != nil {
			http.Error(writer, "failed to encode response", http.StatusInternalServerError)
		}
	}

}
