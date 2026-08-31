package otelsemantics

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"systemtests.weblog/_shared/common"

	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

// Root serves the baseline endpoint used by the HTTP semantics tests.
func Root(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.Header().Set("Content-Length", "13")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("Hello world!\n"))
}

// Status responds with the status code supplied in the code query parameter.
func Status(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(StatusCode(r))
	_, _ = w.Write([]byte("OK"))
}

// StatusCode returns the code query parameter, or 200 when absent or invalid.
func StatusCode(r *http.Request) int {
	if value := r.URL.Query().Get("code"); value != "" {
		if parsed, err := strconv.Atoi(value); err == nil {
			return parsed
		}
	}
	return http.StatusOK
}

// OK responds successfully for route-template and sampling checks.
func OK(w http.ResponseWriter, _ *http.Request) {
	_, _ = w.Write([]byte("OK"))
}

// Healthcheck returns tracer version metadata in the standard weblog format.
func Healthcheck(w http.ResponseWriter, _ *http.Request) {
	healthcheck, err := common.GetHealtchCheck()
	if err != nil {
		http.Error(w, "Can't get JSON data", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(healthcheck); err != nil {
		http.Error(w, "Can't build JSON data", http.StatusInternalServerError)
	}
}

// MakeDistantCall performs a traced downstream request and reports its metadata.
func MakeDistantCall(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Query().Get("url")
	if url == "" {
		_, _ = w.Write([]byte("OK"))
		return
	}

	method := r.URL.Query().Get("method")
	if method == "" {
		method = http.MethodGet
	}

	req, err := http.NewRequestWithContext(r.Context(), method, url, nil)
	if err != nil {
		http.Error(w, "Can't build distant call request", http.StatusBadRequest)
		return
	}

	// WrapClient injects into a clone. Inject explicitly so returned request headers
	// describe propagation performed for this request.
	if span, ok := tracer.SpanFromContext(r.Context()); ok {
		if err := tracer.Inject(span.Context(), tracer.HTTPHeadersCarrier(req.Header)); err != nil {
			http.Error(w, "Can't inject trace context", http.StatusInternalServerError)
			return
		}
	}

	res, err := httptrace.WrapClient(http.DefaultClient).Do(req)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	defer res.Body.Close()

	requestHeaders := make(map[string]string, len(req.Header))
	for key, values := range req.Header {
		requestHeaders[strings.ToLower(key)] = strings.Join(values, ",")
	}
	responseHeaders := make(map[string]string, len(res.Header))
	for key, values := range res.Header {
		responseHeaders[key] = strings.Join(values, ",")
	}

	response := struct {
		URL             string            `json:"url"`
		StatusCode      int               `json:"status_code"`
		RequestHeaders  map[string]string `json:"request_headers"`
		ResponseHeaders map[string]string `json:"response_headers"`
	}{
		URL:             url,
		StatusCode:      res.StatusCode,
		RequestHeaders:  requestHeaders,
		ResponseHeaders: responseHeaders,
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		http.Error(w, "Can't build JSON data", http.StatusInternalServerError)
	}
}
