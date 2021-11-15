package main

import (
	"net/http"

	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start(tracer.WithServiceName("weblog"))
	defer tracer.Stop()
	mux := httptrace.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	mux.HandleFunc("/waf/", func(w http.ResponseWriter, r *http.Request) {
		span, _ := tracer.SpanFromContext(r.Context())
		span.SetTag("http.request.headers.user-agent", r.UserAgent())
		w.Write([]byte("Hello, WAF!"))
	})

	mux.HandleFunc("/sample_rate_route/:i", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	initDatadog()
	http.ListenAndServe(":7777", mux)
}
