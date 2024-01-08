package main

import (
	"context"
	"fmt"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
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
		headers := map[string]string{}
		for _, headerTuple := range args.HttpHeaders.HttpHeaders {
			k := headerTuple.GetKey()
			v := headerTuple.GetValue()
			if k != "" && v != "" {
				headers[k] = v
			}
		}

		sctx, err := tracer.Extract(tracer.TextMapCarrier(headers))
		if err != nil {
			fmt.Println("failed in StartSpan", err, headers)
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
	s.spans = make(map[uint64]*tracer.Span)
	return &FlushSpansReturn{}, nil
}

func (s *apmClientServer) FlushTraceStats(context.Context, *FlushTraceStatsArgs) (*FlushTraceStatsReturn, error) {
	tracer.Flush()
	s.spans = make(map[uint64]*tracer.Span)
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
	span := s.spans[args.SpanId]
	headers := tracer.TextMapCarrier(map[string]string{})
	err := tracer.Inject(span.Context(), headers)
	if err != nil {
		fmt.Println("error while injecting")
	}
	distr := []*HeaderTuple{}
	for k, v := range headers {
		distr = append(distr, &HeaderTuple{Key: k, Value: v})
	}
	return &InjectHeadersReturn{HttpHeaders: &DistributedHTTPHeaders{HttpHeaders: distr}}, nil
}
