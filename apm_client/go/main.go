package main

import (
	"context"
	"flag"
	"fmt"
	"google.golang.org/grpc"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
	"log"
	"net"
)

var (
	port = flag.Int("port", 50051, "The server port")
)

type apmClientServer struct {
	UnimplementedAPMClientServer
	spans map[uint64]tracer.Span
}

func (s *apmClientServer) StartSpan(ctx context.Context, args *StartSpanArgs) (*StartSpanReturn, error) {
	var span tracer.Span
	var opts []tracer.StartSpanOption
	if args.Resource != nil {
		opts = append(opts, tracer.ResourceName(*args.Resource))
	}
	if args.Service != nil {
		opts = append(opts, tracer.ServiceName(*args.Service))
	}
	if args.ParentId != nil && *args.ParentId > 0 {
		parent := s.spans[*args.ParentId]
		opts = append(opts, tracer.ChildOf(parent.Context()))
	}
	span = tracer.StartSpan(args.Name, opts...)
	s.spans[span.Context().SpanID()] = span
	return &StartSpanReturn{
		SpanId:  span.Context().SpanID(),
		TraceId: span.Context().TraceID(),
	}, nil
}

func (s *apmClientServer) SpanSetMeta(ctx context.Context, args *SpanSetMetaArgs) (*SpanSetMetaReturn, error) {
	return &SpanSetMetaReturn{}, nil
}

func (s *apmClientServer) SpanSetMetric(ctx context.Context, args *SpanSetMetricArgs) (*SpanSetMetricReturn, error) {
	return &SpanSetMetricReturn{}, nil
}

func (s *apmClientServer) FinishSpan(ctx context.Context, args *FinishSpanArgs) (*FinishSpanReturn, error) {
	span := s.spans[args.Id]
	span.Finish()
	delete(s.spans, args.Id)
	return &FinishSpanReturn{}, nil
}

func (s *apmClientServer) FlushSpans(context.Context, *FlushSpansArgs) (*FlushSpansReturn, error) {
	tracer.Stop()
	return &FlushSpansReturn{}, nil
}

func (s *apmClientServer) FlushTraceStats(context.Context, *FlushTraceStatsArgs) (*FlushTraceStatsReturn, error) {
	tracer.Stop()
	return &FlushTraceStatsReturn{}, nil
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
	lis, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", *port))
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
