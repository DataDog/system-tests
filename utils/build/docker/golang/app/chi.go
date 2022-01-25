package main

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	chitrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/go-chi/chi.v5"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/ext"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	mux := chi.NewRouter().With(chitrace.Middleware())

	mux.HandleFunc("/waf/", func(w http.ResponseWriter, r *http.Request) {
		span, _ := tracer.SpanFromContext(r.Context())
		span.SetTag("http.request.headers.user-agent", r.UserAgent())
		w.Write([]byte("Hello, WAF!\n"))
	})

	mux.HandleFunc("/*", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	mux.HandleFunc("/sample_rate_route/:i", func(w http.ResponseWriter, r *http.Request) {
		if span, ok := tracer.SpanFromContext(r.Context()); ok {
			span.SetTag(ext.SamplingPriority, ext.PriorityUserKeep)
		}
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/params/:i", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	initDatadog()
	http.ListenAndServe(":7777", mux)
}
