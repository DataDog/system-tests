package common

import (
	"encoding/json"
	"log"
	"net/http"

	of "github.com/open-feature/go-sdk/openfeature"

	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
)

var ofClient *of.Client

func init() {
	ddProvider, err := ddof.NewDatadogProvider()
	if err != nil {
		log.Fatalf("failed to create Datadog OpenFeature provider: %v", err)
	}

	if err := of.SetProviderAndWait(ddProvider); err != nil {
		log.Fatalf("failed to set Datadog OpenFeature provider: %v", err)
	}

	ofClient = of.NewClient("system-tests-weblog-client")
}

func FFeEval(writer http.ResponseWriter, request *http.Request) {
	var body struct {
		Flag          string         `json:"flag"`
		VariationType string         `json:"variationType"`
		DefaultValue  int            `json:"defaultValue"`
		TargetingKey  string         `json:"targetingKey"`
		Attributes    map[string]any `json:"attributes"`
	}
	if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
		http.Error(writer, "invalid request body", http.StatusBadRequest)
		return
	}

	val := ofClient.Object(request.Context(), body.Flag, body.DefaultValue, of.NewEvaluationContext(body.TargetingKey, body.Attributes))

	writer.WriteHeader(http.StatusOK)

	response := struct {
		Value any `json:"value"`
	}{val}

	if err := json.NewEncoder(writer).Encode(response); err != nil {
		http.Error(writer, "failed to encode response", http.StatusInternalServerError)
	}
}
