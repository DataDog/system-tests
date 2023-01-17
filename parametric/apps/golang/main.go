package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"strconv"

	"google.golang.org/grpc"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

type apmClientServer struct {
	UnimplementedAPMClientServer
	spans map[uint64]tracer.Span
}

func (s *apmClientServer) StartSpan(ctx context.Context, args *StartSpanArgs) (*StartSpanReturn, error) {
	var opts []tracer.StartSpanOption
	if args.ParentId != nil && *args.ParentId > 0 {
		parent := s.spans[*args.ParentId]
		opts = append(opts, tracer.ChildOf(parent.Context()))
	}
	if args.Resource != nil {
		opts = append(opts, tracer.ResourceName(*args.Resource))
	}
	if args.Service != nil {
		opts = append(opts, tracer.ServiceName(*args.Service))
	}
	if args.Type != nil {
		opts = append(opts, tracer.SpanType(*args.Type))
	}
	span := tracer.StartSpan(args.Name, opts...)

	if args.Origin != nil {
		span.SetTag("_dd.origin", *args.Origin)
	}
	s.spans[span.Context().SpanID()] = span
	return &StartSpanReturn{
		SpanId:  span.Context().SpanID(),
		TraceId: span.Context().TraceID(),
	}, nil
}

func (s *apmClientServer) SpanSetMeta(ctx context.Context, args *SpanSetMetaArgs) (*SpanSetMetaReturn, error) {
	span := s.spans[args.SpanId]
	span.SetTag(args.Key, args.Value)
	return &SpanSetMetaReturn{}, nil
}

func (s *apmClientServer) SpanSetMetric(ctx context.Context, args *SpanSetMetricArgs) (*SpanSetMetricReturn, error) {
	span := s.spans[args.SpanId]
	span.SetTag(args.Key, args.Value)
	return &SpanSetMetricReturn{}, nil
}

func (s *apmClientServer) FinishSpan(ctx context.Context, args *FinishSpanArgs) (*FinishSpanReturn, error) {
	span := s.spans[args.Id]
	span.Finish()
	return &FinishSpanReturn{}, nil
}

func (s *apmClientServer) FlushSpans(context.Context, *FlushSpansArgs) (*FlushSpansReturn, error) {
	tracer.Flush()
	s.spans = make(map[uint64]tracer.Span)
	return &FlushSpansReturn{}, nil
}

func (s *apmClientServer) FlushTraceStats(context.Context, *FlushTraceStatsArgs) (*FlushTraceStatsReturn, error) {
	tracer.Flush()
	s.spans = make(map[uint64]tracer.Span)
	return &FlushTraceStatsReturn{}, nil
}

func (s *apmClientServer) StopTracer(context.Context, *StopTracerArgs) (*StopTracerReturn, error) {
	tracer.Stop()
	return &StopTracerReturn{}, nil
}

func (s *apmClientServer) SpanSetError(ctx context.Context, args *SpanSetErrorArgs) (*SpanSetErrorReturn, error) {
	span := s.spans[args.SpanId]
	span.SetTag("error", true)
	span.SetTag("error.msg", args.Message)
	span.SetTag("error.type", args.Type)
	span.SetTag("error.stack", args.Stack)
	return &SpanSetErrorReturn{}, nil
}

func newServer() *apmClientServer {
	s := &apmClientServer{
		spans: make(map[uint64]tracer.Span),
	}
	return s
}

func main() {
	tracer.Start()
	defer tracer.Stop()
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
