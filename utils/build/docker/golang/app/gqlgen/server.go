package main

import (
	"context"
	"net/http"
	"weblog/gqlgen/graph"
	"weblog/internal/common"

	graphqltrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/99designs/gqlgen"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"

	"github.com/99designs/gqlgen/graphql/handler"

	_ "github.com/99designs/gqlgen/graphql/introspection" // Register introspection facility
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	srv := handler.NewDefaultServer(graph.NewExecutableSchema(graph.Config{Resolvers: &graph.Resolver{}}))
	srv.Use(graphqltrace.NewTracer())

	mux := http.NewServeMux()
	mux.HandleFunc("/graphql", func(w http.ResponseWriter, r *http.Request) {
		// Store the user-agent in context so we can add it to spans later on...
		r = r.WithContext(context.WithValue(r.Context(), graph.UserAgent{}, r.UserAgent()))
		srv.ServeHTTP(w, r)
	})

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
