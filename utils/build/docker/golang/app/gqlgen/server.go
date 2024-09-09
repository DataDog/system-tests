package main

import (
	"net/http"
	"encoding/json"
	"weblog/gqlgen/graph"
	"weblog/internal/common"

	graphqltrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/99designs/gqlgen"
	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"

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

	mux.HandleFunc("/healthcheck", func(w http.ResponseWriter, r *http.Request) {

		healthCheck, err := common.GetHealtchCheck()
		if err != nil {
			http.Error(w, "Can't get JSON data", http.StatusInternalServerError)
			return
		}

		jsonData, err := json.Marshal(healthCheck)
		if err != nil {
			http.Error(w, "Can't build JSON data", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write(jsonData)
	})

	common.InitDatadog()

	panic(http.ListenAndServe(":7777", mux))
}
