package main

import (
	"net/http"

	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/ext"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func initDatadog() {
	span := tracer.StartSpan("init.service")
	defer span.Finish()
	span.SetTag("whip", "done")
	// avoid the default 0 priority not be removed by the sampler which removes
	// every trace whose span priorities are <= 0 - this feature is configured
	// by the agent and cannot be configured so far
	span.SetTag(ext.SamplingPriority, ext.PriorityUserKeep)
}

// NewWeblogMux implements the expects Weblog HTTP API, factorized into a
// function so that it can be used by the gRPC server too.
func NewWeblogMux() *httptrace.ServeMux {
	mux := httptrace.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// "/" is the default route when the others don't match
		// cf. documentation at https://pkg.go.dev/net/http#ServeMux
		// Therefore, we need to check the URL path to only handle the `/` case
		if r.URL.Path != "/" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		w.WriteHeader(http.StatusOK)
	})

	mux.HandleFunc("/waf/", func(w http.ResponseWriter, r *http.Request) {
		span, _ := tracer.SpanFromContext(r.Context())
		span.SetTag("http.request.headers.user-agent", r.UserAgent())
		write(w, r, []byte("Hello, WAF!"))
	})

	mux.HandleFunc("/sample_rate_route/:i", func(w http.ResponseWriter, r *http.Request) {
		if span, ok := tracer.SpanFromContext(r.Context()); ok {
			span.SetTag(ext.SamplingPriority, ext.PriorityUserKeep)
		}
		w.Write([]byte("OK"))
	})

	return mux
}

func write(w http.ResponseWriter, r *http.Request, d []byte) {
	span, _ := tracer.StartSpanFromContext(r.Context(), "child.span")
	defer span.Finish()
	w.Write(d)
}
