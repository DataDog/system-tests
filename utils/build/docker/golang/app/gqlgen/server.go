package main

import (
	"runtime/debug"
	"net/http"
	"os"
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
		var tracerVersion string
		var libddwafVersion string

		if bi, ok := debug.ReadBuildInfo(); ok {
			for _, mod := range bi.Deps {
				println(mod.Path, mod.Version)

				if mod.Path == "gopkg.in/DataDog/dd-trace-go.v1" {
					tracerVersion = mod.Version
				} else if mod.Path == "github.com/DataDog/go-libddwaf/v3" {
					libddwafVersion = mod.Version
				}
			}
		}

        if tracerVersion == "" {
            http.Error(w, "Can't get dd-trace-go version", http.StatusInternalServerError)
            return
        }

		appsec_rules_version, err := os.ReadFile("SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION")
        if err != nil {
            http.Error(w, "Can't get SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION", http.StatusInternalServerError)
            return
        }
		
        libray := map[string]interface{}{
            "language":  "golang",
            "version":   string(tracerVersion),
            "appsec_event_rules_version": string(appsec_rules_version),
			"libddwaf_version": libddwafVersion,
        }

        data := map[string]interface{}{
            "status": "ok",
            "library": libray,
        }

        jsonData, err := json.Marshal(data)
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
