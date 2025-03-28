package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"
	"systemtests.weblog/gqlgen/graph"

	graphqltrace "github.com/DataDog/dd-trace-go/contrib/99designs/gqlgen/v2"
	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
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

	httpSrv := &http.Server{
		Addr:    ":7777",
		Handler: mux,
	}
	common.InitDatadog()
	go func() {
		if err := httpSrv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, syscall.SIGTERM)
	<-c

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		log.Fatalf("HTTP shutdown error: %v", err)
	}
}
