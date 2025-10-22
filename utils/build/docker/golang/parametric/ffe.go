package main

import (
	"encoding/json"
	"net/http"

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
	}
	if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
		http.Error(writer, "invalid request body: "+err.Error(), http.StatusBadRequest)
		return
	}

	ctx := of.NewEvaluationContext(body.TargetingKey, body.Attributes)
	s.ddProvider.Init(ctx)

	val := s.ofClient.Object(request.Context(), body.Flag, body.DefaultValue, ctx)

	writer.WriteHeader(http.StatusOK)

	response := struct {
		Value any `json:"value"`
	}{val}

	if err := json.NewEncoder(writer).Encode(response); err != nil {
		http.Error(writer, "failed to encode response: "+err.Error(), http.StatusInternalServerError)
	}
}
