package main

import (
	"context"
	"fmt"
	"go.opentelemetry.io/otel/attribute"
	ot_api "go.opentelemetry.io/otel/trace"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace"
	"time"
)

func (s *apmClientServer) OtelStartSpan(ctx context.Context, args *OtelStartSpanArgs) (*OtelStartSpanReturn, error) {
	// todo span options to be expanded
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
	s.otelSpans[ddSpan.Context().SpanID()] = span
	return &OtelStartSpanReturn{
		SpanId:  ddSpan.Context().SpanID(),
		TraceId: ddSpan.Context().SpanID(),
	}, nil
}

func (s *apmClientServer) OtelEndSpan(ctx context.Context, args *OtelEndSpanArgs) (*OtelEndSpanReturn, error) {
	span, ok := s.otelSpans[args.Id]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%d not found", args.Id)
	}
	// todo pass end span options
	span.End()

	return &OtelEndSpanReturn{}, nil
}

func (s *apmClientServer) OtelSetAttributes(ctx context.Context, args *OtelSetAttributesArgs) (*OtelSetAttributesReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%d not found", args.SpanId)
	}

	for k, v := range args.Attributes {
		span.SetAttributes(attribute.String(k, v))

	}
	return &OtelSetAttributesReturn{}, nil
}

func (s *apmClientServer) OtelSetName(ctx context.Context, args *OtelSetNameArgs) (*OtelSetNameReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%d not found", args.SpanId)
	}
	span.SetName(args.Name)
	return &OtelSetNameReturn{}, nil
}

func (s *apmClientServer) OtelFlushSpans(context.Context, *OtelFlushSpansArgs) (*OtelFlushSpansReturn, error) {
	s.otelSpans = make(map[uint64]ot_api.Span)
	return &OtelFlushSpansReturn{}, nil
}

func (s *apmClientServer) OtelFlushTraceStats(context.Context, *OtelFlushTraceStatsArgs) (*OtelFlushTraceStatsReturn, error) {
	s.otelSpans = make(map[uint64]ot_api.Span)
	return &OtelFlushTraceStatsReturn{}, nil
}

func (s *apmClientServer) OtelIsRecording(ctx context.Context, args *OtelIsRecordingArgs) (*OtelIsRecordingReturn, error) {
	//TODO implement me
	panic("implement me")
}

func (s *apmClientServer) OtelSpanContext(ctx context.Context, args *OtelSpanContextArgs) (*OtelSpanContextReturn, error) {
	//TODO implement me
	panic("implement me")
}

func (s *apmClientServer) OtelSetStatus(ctx context.Context, args *OtelSetStatusArgs) (*OtelSetStatusReturn, error) {
	//TODO implement me
	panic("implement me")
}
