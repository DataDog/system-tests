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
	spans map[ot_api.SpanID]ot_api.Span
}

func (s *apmClientServer) StartOtelSpan(ctx context.Context, args *StartOtelSpanArgs) (*StartOtelSpanReturn, error) {
	// todo : move this to StartTracer method
	tp := ot.NewTracerProvider()
	otel.SetTracerProvider(tp)
	tr := otel.Tracer("")

	ctx, span := tr.Start(context.Background(), args.Name)
	spanId := span.SpanContext().SpanID()
	traceId := span.SpanContext().TraceID()
	s.spans[spanId] = span

	return &StartOtelSpanReturn{
		SpanId:  spanId[:],
		TraceId: traceId[:],
	}, nil
}

func (s *apmClientServer) FinishOtelSpan(ctx context.Context, args *FinishOtelSpanArgs) (*FinishOtelSpanReturn, error) {
	var sId *[8]byte
	sId = (*[8]byte)(args.Id)
	span := s.spans[ot_api.SpanID(*sId)]
	span.End()

	return &FinishOtelSpanReturn{}, nil
}

func (s *apmClientServer) FlushSpans(context.Context, *FlushOtelSpansArgs) (*FlushOtelSpansReturn, error) {
	tracer.Flush()
	s.spans = make(map[ot_api.SpanID]ot_api.Span)
	return &FlushOtelSpansReturn{}, nil
}

func (s *apmClientServer) FlushTraceStats(context.Context, *FlushOtelTraceStatsArgs) (*FlushOtelTraceStatsReturn, error) {
	tracer.Flush()
	s.spans = make(map[ot_api.SpanID]ot_api.Span)
	return &FlushOtelTraceStatsReturn{}, nil
}

func (s *apmClientServer) StopTracer(context.Context, *StopOtelTracerArgs) (*StopOtelTracerReturn, error) {
	tracer.Stop()
	return &StopOtelTracerReturn{}, nil
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
