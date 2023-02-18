package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"strconv"

	"go.opentelemetry.io/otel"
	ot_api "go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	ot "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

type apmClientServer struct {
	UnimplementedAPMClientServer
	spans     map[uint64]tracer.Span
	otelSpans map[uint64]ot_api.Span
	tp        *ot.TracerProvider
	tracer    ot_api.Tracer
}

func (s *apmClientServer) StartTracer(context.Context, *StartTracerArgs) (*StartTracerReturn, error) {
	s.tp = ot.NewTracerProvider()
	otel.SetTracerProvider(s.tp)
	//todo tracer options go here
	s.tracer = s.tp.Tracer("")
	return &StartTracerReturn{}, nil
}

func newServer() *apmClientServer {
	s := &apmClientServer{
		spans:     make(map[uint64]tracer.Span),
		otelSpans: make(map[uint64]ot_api.Span),
	}
	return s
}

func main() {
	flag.Parse()
	port, err := strconv.Atoi(os.Getenv("APM_TEST_CLIENT_SERVER_PORT"))
	if err != nil {
		log.Fatalf("failed to convert port to integer: %v", err)
	}
	lis, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", port))
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	s := grpc.NewServer()
	RegisterAPMClientServer(s, newServer())
	log.Printf("server listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
