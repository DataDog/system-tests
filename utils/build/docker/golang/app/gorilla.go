package main

import (
	"net/http"

	muxtrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/gorilla/mux"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/ext"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	mux := muxtrace.NewRouter()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	mux.HandleFunc("/waf/", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("Hello, WAF!\n"))
	})

	mux.HandleFunc("/sample_rate_route/:i", func(w http.ResponseWriter, r *http.Request) {
		if span, ok := tracer.SpanFromContext(r.Context()); ok {
			span.SetTag(ext.SamplingPriority, ext.PriorityUserKeep)
		}
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/params/{value}", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/headers/", func(w http.ResponseWriter, r *http.Request) {
		//Data used for header content is irrelevant here, only header presence is checked
		w.Header().Set("content-type", "text/plain")
		w.Header().Set("content-length", "42")
		w.Header().Set("content-language", "en-US")
		w.Write([]byte("Hello, headers!"))
	})

	initDatadog()
	http.ListenAndServe(":7777", mux)
}
