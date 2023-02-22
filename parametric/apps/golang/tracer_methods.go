package main

import (
	"context"
	"fmt"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func (s *apmClientServer) StartSpan(ctx context.Context, args *StartSpanArgs) (*StartSpanReturn, error) {
	var opts []tracer.StartSpanOption
	if args.GetParentId() > 0 {
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

	if args.GetHttpHeaders() != nil && len(args.HttpHeaders.HttpHeaders) != 0 {
		sctx, err := tracer.NewPropagator(nil).Extract(tracer.TextMapCarrier(args.HttpHeaders.HttpHeaders))
		if err != nil {
			fmt.Println("failed in StartSpan", err, args.HttpHeaders.HttpHeaders)
		} else {
			opts = append(opts, tracer.ChildOf(sctx))
		}
	}
	span := tracer.StartSpan(args.Name, opts...)

	if args.GetOrigin() != "" {
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

func (s *apmClientServer) InjectHeaders(ctx context.Context, args *InjectHeadersArgs) (*InjectHeadersReturn, error) {
	var span tracer.Span
	span, ok := s.spans[args.SpanId]
	if !ok {
		span, ok = s.otelSpans[args.SpanId].(tracer.Span)
		if !ok {
			return nil, fmt.Errorf("no spans found with span_id %v", args.SpanId)
		}
	}
	headers := tracer.TextMapCarrier(map[string]string{})
	err := tracer.Inject(span.Context(), headers)
	if err != nil {
		fmt.Println("error while injecting")
	}
	distr := map[string]string{}
	for k, v := range headers {
		distr[k] = v
	}
	return &InjectHeadersReturn{HttpHeaders: &DistributedHTTPHeaders{HttpHeaders: distr}}, nil
}
