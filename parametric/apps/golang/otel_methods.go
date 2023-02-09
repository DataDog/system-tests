package main

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	ot_api "go.opentelemetry.io/otel/trace"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func (s *apmClientServer) OtelStartSpan(ctx context.Context, args *OtelStartSpanArgs) (*OtelStartSpanReturn, error) {
	// todo span options to be expanded
  var pCtx context.Context = context.Background()
	if pid := args.GetParentId(); pid != "" {
		parent, ok := s.otelSpans[pid]
		if ok {
			pCtx = tracer.ContextWithSpan(context.Background(), parent.(ddtrace.Span))
		}
	}

	var otelOpts = []ot_api.SpanStartOption{
		ot_api.WithSpanKind(ot_api.ValidateSpanKind(ot_api.SpanKind(args.GetSpanKind()))),
	}
	if args.GetNewRoot() {
		otelOpts = append(otelOpts, ot_api.WithNewRoot())
	}
	if t := args.GetTimestamp(); t != 0 {
		tm := time.Unix(t, 0)
		otelOpts = append(otelOpts, ot_api.WithTimestamp(tm))
	}

	// if attrs := args.GetAttributes(); attrs != nil {
	// 	for k, v := range attrs {
	// 		otelOpts = append(otelOpts, ot_api.WithAttributes(attribute.String(k, v)))
	// 	}
	// }

	_, span := s.tp.Tracer("").Start(pCtx, args.Name, otelOpts...)
	s.otelSpans[span.SpanContext().SpanID().String()] = span
	return &OtelStartSpanReturn{
		SpanId: span.SpanContext().SpanID().String(),
	}, nil
}

func (s *apmClientServer) OtelEndSpan(ctx context.Context, args *OtelEndSpanArgs) (*OtelEndSpanReturn, error) {
	span, ok := s.otelSpans[args.Id]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%s not found", args.Id)
	}
	// todo pass end span options
	span.End()

	return &OtelEndSpanReturn{}, nil
}

func (s *apmClientServer) OtelSetAttributes(ctx context.Context, args *OtelSetAttributesArgs) (*OtelSetAttributesReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("SetAttributes call failed, span with id=%s not found", args.SpanId)
	}
	for k, lv := range args.Attributes.KeyVals {
		n := len(lv.GetVal())
		if n == 0 {
			continue
		}
		// all values are represented as slices
		first := lv.GetVal()[0]
		switch first.Val.(type) {
		case *AttrVal_StringVal:
			inp := make([]string, n)
			for _, v := range lv.GetVal() {
				inp = append(inp, v.GetStringVal())
			}
			span.SetAttributes(attribute.StringSlice(k, inp))
		case *AttrVal_BoolVal:
			inp := make([]bool, n)
			for _, v := range lv.GetVal() {
				inp = append(inp, v.GetBoolVal())
			}
			span.SetAttributes(attribute.BoolSlice(k, inp))
		case *AttrVal_DoubleVal:
			inp := make([]float64, n)
			for _, v := range lv.GetVal() {
				inp = append(inp, v.GetDoubleVal())
			}
			span.SetAttributes(attribute.Float64Slice(k, inp))
		case *AttrVal_IntegerVal:
			inp := make([]int64, n)
			for _, v := range lv.GetVal() {
				inp = append(inp, v.GetIntegerVal())
			}
			span.SetAttributes(attribute.Int64Slice(k, inp))
		}

	}
	return &OtelSetAttributesReturn{}, nil
}

func (s *apmClientServer) OtelSetName(ctx context.Context, args *OtelSetNameArgs) (*OtelSetNameReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("EndOtelSpan call failed, span with id=%s not found", args.SpanId)
	}
	span.SetName(args.Name)
	return &OtelSetNameReturn{}, nil
}

func (s *apmClientServer) OtelFlushSpans(ctx context.Context, args *OtelFlushSpansArgs) (*OtelFlushSpansReturn, error) {
	s.otelSpans = make(map[string]ot_api.Span)
	success := false
	set_flush_success := func(ok bool) { success = ok }
	s.tp.ForceFlush(time.Duration(args.Seconds)*time.Second, set_flush_success)
	return &OtelFlushSpansReturn{Success: success}, nil
}

func (s *apmClientServer) OtelFlushTraceStats(context.Context, *OtelFlushTraceStatsArgs) (*OtelFlushTraceStatsReturn, error) {
	s.otelSpans = make(map[string]ot_api.Span)
	return &OtelFlushTraceStatsReturn{}, nil
}

func (s *apmClientServer) OtelIsRecording(ctx context.Context, args *OtelIsRecordingArgs) (*OtelIsRecordingReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Printf("IsRecording call failed, span with id=%s not found", args.SpanId)
	}
	is_recording := span.IsRecording()
	return &OtelIsRecordingReturn{IsRecording: is_recording}, nil
}

func (s *apmClientServer) OtelSpanContext(ctx context.Context, args *OtelSpanContextArgs) (*OtelSpanContextReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Printf("SpanContext call failed, span with id=%s not found", args.SpanId)
	}
	span_context := span.SpanContext()
	spanID := span_context.SpanID().String()
	traceID := span_context.TraceID().String()
	traceFlags := span_context.TraceFlags().String()
	traceState := span_context.TraceState().String()
	remote := span_context.IsRemote()

	return &OtelSpanContextReturn{
		SpanId:     spanID,
		TraceId:    traceID,
		TraceFlags: traceFlags,
		TraceState: traceState,
		Remote:     remote,
	}, nil
}

func (s *apmClientServer) OtelSetStatus(ctx context.Context, args *OtelSetStatusArgs) (*OtelSetStatusReturn, error) {
	span, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("SetStatus call failed, span with id=%d not found", args.SpanId)
	}
	if args.Code == "UNSET" {
		span.SetStatus(codes.Unset, args.Description)
	} else if args.Code == "ERROR" {
		span.SetStatus(codes.Error, args.Description)
	} else if args.Code == "OK" {
		span.SetStatus(codes.Ok, args.Description)
	} else {
		fmt.Sprintf("Invalid code")
	}
	return &OtelSetStatusReturn{}, nil
}
