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
		w.Write([]byte("OK"))
	})

	initDatadog()
	http.ListenAndServe(":7777", mux)
}

func write(w http.ResponseWriter, r *http.Request, d []byte) {
	span, _ := tracer.StartSpanFromContext(r.Context(), "child.span")
	defer span.Finish()
	w.Write(d)
}
