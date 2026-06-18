package common

import (
	"encoding/json"
	"log"
	"net/http"

	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
)

func FFeEval() func(writer http.ResponseWriter, request *http.Request) {
	ddProvider, err := ddof.NewDatadogProvider(ddof.ProviderConfig{})
	if err != nil {
		log.Fatalf("failed to create Datadog OpenFeature provider: %v", err)
	}

	if err := of.SetProvider(ddProvider); err != nil {
		log.Fatalf("failed to set Datadog OpenFeature provider: %v", err)
	}

	ofClient := of.NewClient("system-tests-weblog-client")
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

		ctx := request.Context()
		targetingKeys := body.TargetingKeys
		if len(targetingKeys) == 0 {
			targetingKeys = []string{body.TargetingKey}
		}

		var val any
		for _, targetingKey := range targetingKeys {
			evalCtx := of.NewEvaluationContext(targetingKey, body.Attributes)
			switch body.VariationType {
			case "BOOLEAN":
				defBool, _ := body.DefaultValue.(bool)
				val, _ = ofClient.BooleanValue(ctx, body.Flag, defBool, evalCtx)
			case "STRING":
				defStr, _ := body.DefaultValue.(string)
				val, _ = ofClient.StringValue(ctx, body.Flag, defStr, evalCtx)
			case "INTEGER":
				defFloat, _ := body.DefaultValue.(float64)
				val, _ = ofClient.IntValue(ctx, body.Flag, int64(defFloat), evalCtx)
			case "NUMERIC":
				defFloat, _ := body.DefaultValue.(float64)
				val, _ = ofClient.FloatValue(ctx, body.Flag, defFloat, evalCtx)
			default:
				val = ofClient.Object(ctx, body.Flag, body.DefaultValue, evalCtx)
			}
		}

		writer.WriteHeader(http.StatusOK)

		response := struct {
			Value any `json:"value"`
			Count int `json:"count"`
		}{val, len(targetingKeys)}

		if err := json.NewEncoder(writer).Encode(response); err != nil {
			http.Error(writer, "failed to encode response", http.StatusInternalServerError)
		}
	}

}
