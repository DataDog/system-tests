package main

import (
	"context"
	"flag"
	"fmt"
	"go.opentelemetry.io/otel"
	"log"
	"net"
	"os"
	"strconv"

	ot_api "go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	ot "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"

	_ "sync/atomic"
)

type apmClientServer struct {
	UnimplementedAPMOtelClientServer
	tracer ot_api.Tracer
	spans  map[ot_api.SpanID]ot_api.Span
}

func (s *apmClientServer) StartOtelSpan(ctx context.Context, args *StartOtelSpanArgs) (*StartOtelSpanReturn, error) {
	ctx, span := s.tracer.Start(context.Background(), args.Name)
	spanId := span.SpanContext().SpanID()
	traceId := span.SpanContext().TraceID()
	s.spans[spanId] = span

	return &StartOtelSpanReturn{
		SpanId:  spanId[:],
		TraceId: traceId[:],
	}, nil
}

func (s *apmClientServer) EndOtelSpan(ctx context.Context, args *EndOtelSpanArgs) (*EndOtelSpanReturn, error) {
	var sId *[8]byte
	sId = (*[8]byte)(args.Id)
	span := s.spans[ot_api.SpanID(*sId)]
	span.End()

	return &EndOtelSpanReturn{}, nil
}

func (s *apmClientServer) FlushOtelSpans(context.Context, *FlushOtelSpansArgs) (*FlushOtelSpansReturn, error) {
	tracer.Flush()
	s.spans = make(map[ot_api.SpanID]ot_api.Span)
	return &FlushOtelSpansReturn{}, nil
}

func (s *apmClientServer) FlushOtelTraceStats(context.Context, *FlushOtelTraceStatsArgs) (*FlushOtelTraceStatsReturn, error) {
	tracer.Flush()
	s.spans = make(map[ot_api.SpanID]ot_api.Span)
	return &FlushOtelTraceStatsReturn{}, nil
}

func (s *apmClientServer) StopOtelTracer(context.Context, *StopOtelTracerArgs) (*StopOtelTracerReturn, error) {
	tracer.Stop()
	return &StopOtelTracerReturn{}, nil
}

func (s *apmClientServer) StartOtelTracer(context.Context, *StartOtelTracerArgs) (*StartOtelTracerReturn, error) {
	tp := ot.NewTracerProvider()
	otel.SetTracerProvider(tp)
	s.tracer = otel.Tracer("")
	return &StartOtelTracerReturn{}, nil
}

func newServer() *apmClientServer {
	s := &apmClientServer{
		spans: make(map[ot_api.SpanID]ot_api.Span),
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
	RegisterAPMOtelClientServer(s, newServer())
	log.Printf("server listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
