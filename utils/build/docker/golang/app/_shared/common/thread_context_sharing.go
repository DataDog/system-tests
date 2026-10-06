package common

import (
	"encoding/json"
	"math/big"
	"net/http"
	"os"
	"strconv"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

func ThreadContextSharing(w http.ResponseWriter, r *http.Request) {
	span, ok := tracer.SpanFromContext(r.Context())
	if !ok {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	path := r.URL.Query().Get("path")
	if err := os.WriteFile(path, []byte("system-tests thread context sharing"), 0o644); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// SpanContext.TraceID() returns the full 128-bit trace id as a hex string;
	// convert it to decimal to match the other weblogs' response format.
	traceID, ok := new(big.Int).SetString(span.Context().TraceID(), 16)
	if !ok {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	jsonResponse, err := json.Marshal(struct {
		TraceID string `json:"trace_id"`
		SpanID  string `json:"span_id"`
	}{
		TraceID: traceID.String(),
		SpanID:  strconv.FormatUint(span.Context().SpanID(), 10),
	})
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if _, err := w.Write(jsonResponse); err != nil {
		return
	}
}
