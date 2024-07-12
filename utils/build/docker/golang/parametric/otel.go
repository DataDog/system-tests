package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	otel_trace "go.opentelemetry.io/otel/trace"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace"
	ddotel "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func ConvertKeyValsToAttributes(keyVals map[string]*ListVal) map[string][]attribute.KeyValue {
	attributes := make([]attribute.KeyValue, 0, len(keyVals))
	attributesStringified := make([]attribute.KeyValue, 0, len(keyVals))
	for k, lv := range keyVals {
		n := len(lv.GetVal())
		if n == 0 {
			continue
		}
		// all values are represented as slices
		first := lv.GetVal()[0]
		switch first.Val.(type) {
		case *AttrVal_StringVal:
			inp := make([]string, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetStringVal()
			}
			attributesStringified = append(attributesStringified, attribute.String(k, "["+strings.Join(inp, ", ")+"]"))
			if len(inp) > 1 {
				attributes = append(attributes, attribute.StringSlice(k, inp))
			} else {
				attributes = append(attributes, attribute.String(k, inp[0]))
			}
		case *AttrVal_BoolVal:
			inp := make([]bool, n)
			stringifiedInp := make([]string, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetBoolVal()
				stringifiedInp[i] = strconv.FormatBool(v.GetBoolVal())
			}
			attributesStringified = append(attributesStringified, attribute.String(k, "["+strings.Join(stringifiedInp, ", ")+"]"))
			if len(inp) > 1 {
				attributes = append(attributes, attribute.BoolSlice(k, inp))
			} else {
				attributes = append(attributes, attribute.Bool(k, inp[0]))
			}
		case *AttrVal_DoubleVal:
			inp := make([]float64, n)
			stringifiedInp := make([]string, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetDoubleVal()
				stringifiedInp[i] = strconv.FormatFloat(v.GetDoubleVal(), 'f', -1, 64)
			}
			attributesStringified = append(attributesStringified, attribute.String(k, "["+strings.Join(stringifiedInp, ", ")+"]"))
			if len(inp) > 1 {
				attributes = append(attributes, attribute.Float64Slice(k, inp))
			} else {
				attributes = append(attributes, attribute.Float64(k, inp[0]))
			}
		case *AttrVal_IntegerVal:
			inp := make([]int64, n)
			stringifiedInp := make([]string, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetIntegerVal()
				stringifiedInp[i] = strconv.FormatInt(v.GetIntegerVal(), 10)
			}
			attributesStringified = append(attributesStringified, attribute.String(k, "["+strings.Join(stringifiedInp, ", ")+"]"))
			if len(inp) > 1 {
				attributes = append(attributes, attribute.Int64Slice(k, inp))
			} else {
				attributes = append(attributes, attribute.Int64(k, inp[0]))
			}
		}
	}
	return map[string][]attribute.KeyValue{
		"0": attributes,
		"1": attributesStringified,
	}
}

func (s *apmClientServer) OtelStartSpan(ctx context.Context, args *OtelStartSpanArgs) (*OtelStartSpanReturn, error) {
	if s.tracer == nil {
		s.tracer = s.tp.Tracer("")
	}
	var pCtx = context.Background()
	var ddOpts []tracer.StartSpanOption
	if pid := args.GetParentId(); pid != 0 {
		parent, ok := s.otelSpans[pid]
		if ok {
			pCtx = parent.ctx
		}
	}
	var otelOpts []otel_trace.SpanStartOption
	if args.SpanKind != nil {
		otelOpts = append(otelOpts, otel_trace.WithSpanKind(otel_trace.ValidateSpanKind(otel_trace.SpanKind(args.GetSpanKind()))))
	}
	if t := args.GetTimestamp(); t != 0 {
		tm := time.UnixMicro(t)
		otelOpts = append(otelOpts, otel_trace.WithTimestamp(tm))
	}
	if args.GetAttributes() != nil {
		otelOpts = append(otelOpts, otel_trace.WithAttributes(ConvertKeyValsToAttributes(args.GetAttributes().KeyVals)["0"]...))
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
		sctx, err := tracer.NewPropagator(nil).Extract(tracer.TextMapCarrier(headers))
		if err != nil {
			fmt.Println("failed in StartSpan", err, args.HttpHeaders.HttpHeaders)
		} else {
			ddOpts = append(ddOpts, tracer.ChildOf(sctx))
		}
	}

	if links := args.GetSpanLinks(); links != nil {
		for _, link := range links {
			switch from := link.From.(type) {
			case *SpanLink_ParentId:
				if _, ok := s.otelSpans[from.ParentId]; ok {
					otelOpts = append(otelOpts, otel_trace.WithLinks(otel_trace.Link{SpanContext: s.otelSpans[from.ParentId].span.SpanContext(), Attributes: ConvertKeyValsToAttributes(link.GetAttributes().KeyVals)["1"]}))
				}
			case *SpanLink_HttpHeaders:
				headers := map[string]string{}
				for _, headerTuple := range from.HttpHeaders.HttpHeaders {
					k := headerTuple.GetKey()
					v := headerTuple.GetValue()
					if k != "" && v != "" {
						headers[k] = v
					}
				}
				extractedContext, _ := tracer.NewPropagator(nil).Extract(tracer.TextMapCarrier(headers))
				state, _ := otel_trace.ParseTraceState(headers["tracestate"])

				var traceID otel_trace.TraceID
				var spanID otel_trace.SpanID
				if w3cCtx, ok := extractedContext.(ddtrace.SpanContextW3C); ok {
					traceID = w3cCtx.TraceID128Bytes()
				} else {
					fmt.Printf("Non-W3C context found in span, unable to get full 128 bit trace id")
					uint64ToByte(extractedContext.TraceID(), traceID[:])
				}
				uint64ToByte(extractedContext.SpanID(), spanID[:])
				config := otel_trace.SpanContextConfig{
					TraceID:    traceID,
					SpanID:     spanID,
					TraceState: state,
				}
				var newCtx = otel_trace.NewSpanContext(config)
				otelOpts = append(otelOpts, otel_trace.WithLinks(otel_trace.Link{
					SpanContext: newCtx,
					Attributes:  ConvertKeyValsToAttributes(link.GetAttributes().KeyVals)["1"],
				}))
			}

		}
	}

	ctx, span := s.tracer.Start(ddotel.ContextWithStartOptions(pCtx, ddOpts...), args.Name, otelOpts...)
	hexSpanId := hex2int(span.SpanContext().SpanID().String())
	s.otelSpans[hexSpanId] = spanContext{
		span: span,
		ctx:  ctx,
	}

	return &OtelStartSpanReturn{
		SpanId:  hexSpanId,
		TraceId: hex2int(span.SpanContext().TraceID().String()),
	}, nil
}

func uint64ToByte(n uint64, b []byte) {
	binary.BigEndian.PutUint64(b, n)
}

func (s *apmClientServer) OtelEndSpan(ctx context.Context, args *OtelEndSpanArgs) (*OtelEndSpanReturn, error) {
	sctx, ok := s.otelSpans[args.Id]
	if !ok {
		fmt.Sprintf("OtelEndSpan call failed, span with id=%span not found", args.Id)
	}
	endOpts := []otel_trace.SpanEndOption{}
	if t := args.GetTimestamp(); t != 0 {
		tm := time.UnixMicro(t)
		endOpts = append(endOpts, otel_trace.WithTimestamp(tm))
	}
	sctx.span.End(endOpts...)
	return &OtelEndSpanReturn{}, nil
}

func (s *apmClientServer) OtelSetAttributes(ctx context.Context, args *OtelSetAttributesArgs) (*OtelSetAttributesReturn, error) {
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("OtelSetAttributes call failed, span with id=%s not found", args.SpanId)
	}
	span := sctx.span
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
			for i, v := range lv.GetVal() {
				inp[i] = v.GetStringVal()
			}
			if len(inp) > 1 {
				span.SetAttributes(attribute.StringSlice(k, inp))
			} else {
				span.SetAttributes(attribute.String(k, inp[0]))
			}
		case *AttrVal_BoolVal:
			inp := make([]bool, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetBoolVal()
			}
			if len(inp) > 1 {
				span.SetAttributes(attribute.BoolSlice(k, inp))
			} else {
				span.SetAttributes(attribute.Bool(k, inp[0]))
			}
		case *AttrVal_DoubleVal:
			inp := make([]float64, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetDoubleVal()
			}
			if len(inp) > 1 {
				span.SetAttributes(attribute.Float64Slice(k, inp))
			} else {
				span.SetAttributes(attribute.Float64(k, inp[0]))
			}
		case *AttrVal_IntegerVal:
			inp := make([]int64, n)
			for i, v := range lv.GetVal() {
				inp[i] = v.GetIntegerVal()
			}
			if len(inp) > 1 {
				span.SetAttributes(attribute.Int64Slice(k, inp))
			} else {
				span.SetAttributes(attribute.Int64(k, inp[0]))
			}
		}

	}
	return &OtelSetAttributesReturn{}, nil
}

func (s *apmClientServer) OtelSetName(ctx context.Context, args *OtelSetNameArgs) (*OtelSetNameReturn, error) {
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("OtelSetName call failed, span with id=%span not found", args.SpanId)
	}
	sctx.span.SetName(args.Name)
	return &OtelSetNameReturn{}, nil
}

func (s *apmClientServer) OtelFlushSpans(ctx context.Context, args *OtelFlushSpansArgs) (*OtelFlushSpansReturn, error) {
	s.otelSpans = make(map[uint64]spanContext)
	success := false
	s.tp.ForceFlush(time.Duration(args.Seconds)*time.Second, func(ok bool) { success = ok })
	return &OtelFlushSpansReturn{Success: success}, nil
}

func (s *apmClientServer) OtelFlushTraceStats(context.Context, *OtelFlushTraceStatsArgs) (*OtelFlushTraceStatsReturn, error) {
	s.otelSpans = make(map[uint64]spanContext)
	return &OtelFlushTraceStatsReturn{}, nil
}

func (s *apmClientServer) OtelIsRecording(ctx context.Context, args *OtelIsRecordingArgs) (*OtelIsRecordingReturn, error) {
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Printf("OtelIsRecording call failed, span with id=%span not found", args.SpanId)
	}
	return &OtelIsRecordingReturn{IsRecording: sctx.span.IsRecording()}, nil
}

func (s *apmClientServer) OtelSpanContext(ctx context.Context, args *OtelSpanContextArgs) (*OtelSpanContextReturn, error) {
	sctx, ok := s.otelSpans[(args.SpanId)]
	if !ok {
		fmt.Printf("OtelSpanContext call failed, span with id=%span not found", args.SpanId)
	}
	sc := sctx.span.SpanContext()
	return &OtelSpanContextReturn{
		SpanId:     sc.SpanID().String(),
		TraceId:    sc.TraceID().String(),
		TraceFlags: sc.TraceFlags().String(),
		TraceState: sc.TraceState().String(),
		Remote:     sc.IsRemote(),
	}, nil
}

func (s *apmClientServer) OtelAddEvent(ctx context.Context, args *OtelAddEventArgs) (*OtelAddEventReturn, error) {
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Printf("OtelSetStatus call failed, span with id=%d not found", args.SpanId)
	}
	span := sctx.span
	opts := []otel_trace.EventOption{}
	if args.Timestamp != nil {
		opts = append(opts, otel_trace.WithTimestamp(time.Unix(0, *args.Timestamp)))
	}
	if args.GetAttributes() != nil {
		opts = append(opts, otel_trace.WithAttributes(ConvertKeyValsToAttributes(args.GetAttributes().KeyVals)["0"]...))
	}
	span.AddEvent(args.Name, opts...)
	return &OtelAddEventReturn{}, nil
}

func (s *apmClientServer) OtelSetStatus(ctx context.Context, args *OtelSetStatusArgs) (*OtelSetStatusReturn, error) {
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		fmt.Sprintf("OtelSetStatus call failed, span with id=%d not found", args.SpanId)
	}
	span := sctx.span
	switch args.Code {
	case "UNSET":
		span.SetStatus(codes.Unset, args.Description)
	case "ERROR":
		span.SetStatus(codes.Error, args.Description)
	case "OK":
		span.SetStatus(codes.Ok, args.Description)
	default:
		fmt.Sprintf("Invalid code")
	}
	return &OtelSetStatusReturn{}, nil
}

func hex2int(hexStr string) uint64 {
	// remove 0x suffix if found in the input string
	cleaned := strings.Replace(hexStr, "0x", "", -1)

	// base 16 for hexadecimal
	result, err := strconv.ParseUint(cleaned, 16, 64)
	if err != nil {
		fmt.Printf("Converting hex string to uint64 failed, hex string : %s\n", hexStr)
	}
	return result
}
