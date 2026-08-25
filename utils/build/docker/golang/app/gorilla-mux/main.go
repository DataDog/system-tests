package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"
	semantics "systemtests.weblog/_shared/otel_semantics"

	muxtrace "github.com/DataDog/dd-trace-go/contrib/gorilla/mux/v2"
	_ "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/metric"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/gorilla/mux"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	router := muxtrace.NewRouter()
	registerRoutes(router.Router)

	server := &http.Server{Addr: ":7777", Handler: router}
	common.InitDatadog()
	go func() {
		if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			panic(err)
		}
	}()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM)
	<-signals

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		panic(err)
	}
}

func registerRoutes(router *mux.Router) {
	router.HandleFunc("/", semantics.Root)
	router.HandleFunc("/status", semantics.Status)
	router.HandleFunc("/sample_rate_route/{i}", semantics.OK)
	router.HandleFunc("/make_distant_call", semantics.MakeDistantCall)
	router.HandleFunc("/healthcheck", semantics.Healthcheck)
}
