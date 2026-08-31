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

	restfultrace "github.com/DataDog/dd-trace-go/contrib/emicklei/go-restful.v3/v2"
	_ "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/metric"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/emicklei/go-restful/v3"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	container := restful.NewContainer()
	container.Filter(restfultrace.FilterFunc())

	service := new(restful.WebService)
	service.Route(service.GET("/").To(restfulHandler(semantics.Root)))
	service.Route(service.GET("/status").To(func(request *restful.Request, response *restful.Response) {
		response.WriteHeader(semantics.StatusCode(request.Request))
		_, _ = response.Write([]byte("OK"))
	}))
	service.Route(service.GET("/sample_rate_route/{i}").To(restfulHandler(semantics.OK)))
	service.Route(service.GET("/make_distant_call").To(restfulHandler(semantics.MakeDistantCall)))
	service.Route(service.GET("/healthcheck").To(restfulHandler(semantics.Healthcheck)))
	container.Add(service)

	server := &http.Server{Addr: ":7777", Handler: container}
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

func restfulHandler(handler http.HandlerFunc) restful.RouteFunction {
	return func(request *restful.Request, response *restful.Response) {
		handler(response.ResponseWriter, request.Request)
	}
}
