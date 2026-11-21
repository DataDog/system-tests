package common

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"reflect"
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
		var body ffeRequest
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

		ffeRespond(writer, request, ofClient, body)
	}

}

// FFeProviderOptionsEval evaluates like FFeEval, through an OpenFeature domain whose Datadog provider is
// built with the requested EvaluationTelemetryEnabled and ExposuresEnabled options, one provider per
// combination. The options are set by name so the weblog still builds against SDKs without them,
// which answer 501.
func FFeProviderOptionsEval() func(writer http.ResponseWriter, request *http.Request) {
	var mutex sync.Mutex
	clients := map[string]*of.Client{}

	optionClient := func(evaluationTelemetry, exposures bool) (*of.Client, int, error) {
		mutex.Lock()
		defer mutex.Unlock()

		domain := fmt.Sprintf("telemetry-%t-exposures-%t", evaluationTelemetry, exposures)
		if client, ok := clients[domain]; ok {
			return client, 0, nil
		}
		var config ddof.ProviderConfig
		for name, enabled := range map[string]bool{
			"EvaluationTelemetryEnabled": evaluationTelemetry,
			"ExposuresEnabled":           exposures,
		} {
			field := reflect.ValueOf(&config).Elem().FieldByName(name)
			if !field.IsValid() || field.Type() != reflect.TypeOf((*bool)(nil)) {
				return nil, http.StatusNotImplemented, fmt.Errorf("ProviderConfig does not support %s", name)
			}
			field.Set(reflect.ValueOf(&enabled))
		}
		provider, err := ddof.NewDatadogProvider(config)
		if err != nil {
			return nil, http.StatusInternalServerError, fmt.Errorf("create Datadog OpenFeature provider: %w", err)
		}
		if err := of.SetNamedProviderAndWait(domain, provider); err != nil {
			return nil, http.StatusInternalServerError, fmt.Errorf("set Datadog OpenFeature provider: %w", err)
		}
		client := of.NewClient(domain)
		clients[domain] = client
		return client, 0, nil
	}

	return func(writer http.ResponseWriter, request *http.Request) {
		var body struct {
			ffeRequest
			EvaluationTelemetryEnabled *bool `json:"evaluationTelemetryEnabled"`
			ExposuresEnabled           *bool `json:"exposuresEnabled"`
		}
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			http.Error(writer, "invalid request body", http.StatusBadRequest)
			return
		}

		client, status, err := optionClient(
			body.EvaluationTelemetryEnabled == nil || *body.EvaluationTelemetryEnabled,
			body.ExposuresEnabled == nil || *body.ExposuresEnabled,
		)
		if err != nil {
			log.Printf("failed to create the Datadog OpenFeature provider: %v", err)
			errorCode := "GENERAL"
			if status == http.StatusNotImplemented {
				errorCode = "UNSUPPORTED"
			}
			writer.Header().Set("Content-Type", "application/json")
			writer.WriteHeader(status)
			_ = json.NewEncoder(writer).Encode(map[string]string{"errorCode": errorCode, "errorMessage": err.Error()})
			return
		}

		ffeRespond(writer, request, client, body.ffeRequest)
	}
}

type ffeRequest struct {
	Flag          string         `json:"flag"`
	VariationType string         `json:"variationType"`
	DefaultValue  any            `json:"defaultValue"`
	TargetingKey  string         `json:"targetingKey"`
	TargetingKeys []string       `json:"targetingKeys"`
	Attributes    map[string]any `json:"attributes"`
}

func ffeRespond(writer http.ResponseWriter, request *http.Request, ofClient *of.Client, body ffeRequest) {
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
