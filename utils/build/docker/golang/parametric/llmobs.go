package main

import "net/http"

var llmObsExportHandlerImpl = func(_ *apmClientServer, w http.ResponseWriter, _ *http.Request) {
	http.Error(w, "offline LLM Obs export is unavailable in this tracer version", http.StatusNotImplemented)
}

func (s *apmClientServer) llmObsExportHandler(w http.ResponseWriter, r *http.Request) {
	llmObsExportHandlerImpl(s, w, r)
}
