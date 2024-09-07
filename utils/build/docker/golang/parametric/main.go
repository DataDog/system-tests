package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"strconv"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"go.opentelemetry.io/otel"
	"google.golang.org/grpc"

	ddotel "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry"
	otel_trace "go.opentelemetry.io/otel/trace"
)

type apmClientServer struct {
	UnimplementedAPMClientServer
	spans     map[uint64]*tracer.Span
	otelSpans map[uint64]spanContext
	tp        *ddotel.TracerProvider
	tracer    otel_trace.Tracer
}

type spanContext struct {
	span otel_trace.Span
	ctx  context.Context
}

func newServer() *apmClientServer {
	s := &apmClientServer{
		spans:     make(map[uint64]*tracer.Span),
		otelSpans: make(map[uint64]spanContext),
	}
	s.tp = ddotel.NewTracerProvider()
	otel.SetTracerProvider(s.tp)
	return s
}

func main() {
	flag.Parse()
	defer func() {
		if err := recover(); err != nil {
			log.Print("encountered unexpected panic", err)
		}
	}()
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
