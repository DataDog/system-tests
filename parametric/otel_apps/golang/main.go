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
	"time"

	"go.opentelemetry.io/otel/attribute"
	ot_api "go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace"
	ot "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

type apmClientServer struct {
	UnimplementedAPMOtelClientServer
	tp     *ot.TracerProvider
	tracer ot_api.Tracer
	spans  map[uint64]ot_api.Span
}

func (s *apmClientServer) StartOtelSpan(ctx context.Context, args *StartOtelSpanArgs) (*StartOtelSpanReturn, error) {
	fmt.Println("started_StartOtelSpan")
	//todo tracer options/ span parent context not passed
	//var pCtx = context.Background()
	//if args.ParentId != nil && *args.ParentId > 0 {
	//	parent := s.spans[*args.ParentId]
	//	ddP, ok := parent.(ddtrace.Span)
	//	pCtx = tracer.ContextWithSpan(ctx, ddP)
	//}
	var otelOpts = []ot_api.SpanStartOption{
		ot_api.WithSpanKind(ot_api.SpanKind(args.GetSpanKind())),
	}
	if args.GetNewRoot() {
		otelOpts = append(otelOpts, ot_api.WithNewRoot())
	}
	if t := args.GetTimestamp(); t != 0 {
		tm := time.Unix(t, 0)
		otelOpts = append(otelOpts, ot_api.WithTimestamp(tm))
	}
	if attrs := args.GetAttributes(); attrs != nil {
		for k, v := range attrs.Tags {
			otelOpts = append(otelOpts, ot_api.WithAttributes(attribute.String(k, v)))
		}
	}
	ctx, span := s.tp.Tracer("").Start(context.Background(), args.Name, otelOpts...)
	ddSpan, ok := span.(ddtrace.Span)
	if !ok {
		fmt.Println("span must be of ddtrace.Span type")
	}
	s.spans[ddSpan.Context().SpanID()] = span
	return &StartOtelSpanReturn{
		SpanId:  ddSpan.Context().SpanID(),
		TraceId: ddSpan.Context().SpanID(),
	}, nil
}

func (s *apmClientServer) EndOtelSpan(ctx context.Context, args *EndOtelSpanArgs) (*EndOtelSpanReturn, error) {
	span, ok := s.spans[args.Id]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%d not found", args.Id)
	}
	// todo pass end span options
	span.End()

	return &EndOtelSpanReturn{}, nil
}

func (s *apmClientServer) SetAttributes(ctx context.Context, args *SetAttributesArgs) (*SetAttributesReturn, error) {
	span, ok := s.spans[args.SpanId]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%d not found", args.SpanId)
	}

	for k, v := range args.Attributes {
		span.SetAttributes(attribute.String(k, v))

	}
	return &SetAttributesReturn{}, nil
}

func (s *apmClientServer) SetName(ctx context.Context, args *SetNameArgs) (*SetNameReturn, error) {
	span, ok := s.spans[args.SpanId]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%d not found", args.SpanId)
	}
	span.SetName(args.Name)
	return &SetNameReturn{}, nil
}

func (s *apmClientServer) FlushOtelSpans(context.Context, *FlushOtelSpansArgs) (*FlushOtelSpansReturn, error) {
	s.spans = make(map[uint64]ot_api.Span)
	return &FlushOtelSpansReturn{}, nil
}

func (s *apmClientServer) FlushOtelTraceStats(context.Context, *FlushOtelTraceStatsArgs) (*FlushOtelTraceStatsReturn, error) {
	s.spans = make(map[uint64]ot_api.Span)
	return &FlushOtelTraceStatsReturn{}, nil
}

func (s *apmClientServer) StopOtelTracer(context.Context, *StopOtelTracerArgs) (*StopOtelTracerReturn, error) {
	tracer.Stop()
	return &StopOtelTracerReturn{}, nil
}

func (s *apmClientServer) StartOtelTracer(context.Context, *StartOtelTracerArgs) (*StartOtelTracerReturn, error) {
	s.tp = ot.NewTracerProvider()
	otel.SetTracerProvider(s.tp)
	//todo tracer options go here
	s.tracer = s.tp.Tracer("")
	return &StartOtelTracerReturn{}, nil
}

func newServer() *apmClientServer {
	s := &apmClientServer{
		spans: make(map[uint64]ot_api.Span),
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
