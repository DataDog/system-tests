package main

import (
	"net/http"
	"weblog/gqlgen/graph"
	"weblog/internal/common"

	graphqltrace "github.com/DataDog/dd-trace-go/v2/contrib/99designs/gqlgen"
	httptrace "github.com/DataDog/dd-trace-go/v2/contrib/net/http"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"

	"github.com/99designs/gqlgen/graphql/handler"

	_ "github.com/99designs/gqlgen/graphql/introspection" // Register introspection facility
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	srv := handler.NewDefaultServer(graph.NewExecutableSchema(graph.Config{Resolvers: &graph.Resolver{}}))
	srv.Use(graphqltrace.NewTracer())

	mux := httptrace.NewServeMux()
	mux.Handle("/graphql", srv)

	// The / endpoint is used as a weblog heartbeat
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

	common.InitDatadog()

	panic(http.ListenAndServe(":7777", mux))
}
