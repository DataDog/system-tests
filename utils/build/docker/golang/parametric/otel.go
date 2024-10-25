package main

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel/codes"
	otel_trace "go.opentelemetry.io/otel/trace"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace"
	ddotel "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func (s *apmClientServer) otelStartSpanHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelStartSpanArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	fmt.Println("MTOFF: ARGS!!!", args.Attributes)

	result, err := s.OtelStartSpan(&args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(result); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *apmClientServer) OtelStartSpan(args *OtelStartSpanArgs) (*OtelStartSpanReturn, error) {
	if s.tracer == nil {
		s.tracer = s.tp.Tracer("")
	}
	var pCtx = context.Background()
	var ddOpts []tracer.StartSpanOption
	if pid := args.ParentId; pid != 0 {
		parent, ok := s.otelSpans[pid]
		if ok {
			pCtx = parent.ctx
		}
	}
	var otelOpts []otel_trace.SpanStartOption
	if args.SpanKind != 0 {
		otelOpts = append(otelOpts, otel_trace.WithSpanKind(otel_trace.ValidateSpanKind(otel_trace.SpanKind(args.SpanKind))))
	}
	if t := args.Timestamp; t != 0 {
		tm := time.UnixMicro(t)
		otelOpts = append(otelOpts, otel_trace.WithTimestamp(tm))
	}
	if a := args.GetAttributes(); len(a) > 0 {
		fmt.Println("MTOFF: We have attributes:", args.GetAttributes())
		otelOpts = append(otelOpts, otel_trace.WithAttributes(a.ConvertToAttributes()...))
	}
	if len(args.HttpHeaders) > 0 {
		headers := map[string]string{}
		for _, headerTuple := range args.HttpHeaders {
			k := headerTuple.GetKey()
			v := headerTuple.GetValue()
			if k != "" && v != "" {
				headers[k] = v
			}
		}
		sctx, err := tracer.NewPropagator(nil).Extract(tracer.TextMapCarrier(headers))
		if err != nil {
			fmt.Println("failed in StartSpan", err, args.HttpHeaders)
		} else {
			ddOpts = append(ddOpts, tracer.ChildOf(sctx))
		}
	}

	if links := args.SpanLinks; links != nil {
		for _, link := range links {
			switch from := link.From.(type) {
			case *SpanLink_ParentId:
				if _, ok := s.otelSpans[from.ParentId]; ok {
					otelOpts = append(otelOpts, otel_trace.WithLinks(otel_trace.Link{SpanContext: s.otelSpans[from.ParentId].span.SpanContext(), Attributes: link.GetAttributes().ConvertToAttributesStringified()}))
				}
			case *SpanLink_HttpHeaders:
				headers := map[string]string{}
				for _, headerTuple := range *from.HttpHeaders {
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
					Attributes:  link.GetAttributes().ConvertToAttributesStringified(),
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

func (s *apmClientServer) otelEndSpanHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelEndSpanArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelEndSpan(&args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelEndSpan(args *OtelEndSpanArgs) error {
	sctx, ok := s.otelSpans[args.Id]
	if !ok {
		fmt.Printf("OtelEndSpan call failed, span with id=%d not found", args.Id)
		return fmt.Errorf("span with id=%d not found", args.Id)
	}

	endOpts := []otel_trace.SpanEndOption{}
	if t := args.GetTimestamp(); t != 0 {
		tm := time.UnixMicro(t)
		endOpts = append(endOpts, otel_trace.WithTimestamp(tm))
	}

	sctx.span.End(endOpts...)
	return nil
}

func (s *apmClientServer) otelSetAttributesHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelSetAttributesArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelSetAttributes(context.Background(), &args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelSetAttributes(ctx context.Context, args *OtelSetAttributesArgs) error {
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		return fmt.Errorf("OtelSetAttributes call failed, span with id=%d not found", args.SpanId)
	}
	span := sctx.span
	span.SetAttributes(args.Attributes.ConvertToAttributes()...)
	return nil
}

func (s *apmClientServer) otelSetNameHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelSetNameArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		http.Error(w, fmt.Sprintf("OtelSetName call failed, span with id=%d not found", args.SpanId), http.StatusInternalServerError)
	}
	sctx.span.SetName(args.Name)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) otelFlushSpansHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelFlushSpansArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	s.otelSpans = make(map[uint64]spanContext)
	success := false
	s.tp.ForceFlush(time.Duration(args.Seconds)*time.Second, func(ok bool) { success = ok })
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&OtelFlushSpansReturn{Success: success}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *apmClientServer) otelFlushTraceStatsHandler(w http.ResponseWriter, _ *http.Request) {
	s.otelSpans = make(map[uint64]spanContext)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) otelIsRecordingHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelIsRecordingArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		http.Error(w, fmt.Sprintf("OtelIsRecording call failed, span with id=%d not found", args.SpanId), http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&OtelIsRecordingReturn{IsRecording: sctx.span.IsRecording()}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *apmClientServer) otelSpanContextHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelSpanContextArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	sctx, ok := s.otelSpans[(args.SpanId)]
	if !ok {
		http.Error(w, fmt.Sprintf("OtelSpanContext call failed, span with id=%d not found", args.SpanId), http.StatusBadRequest)
		return
	}
	sc := sctx.span.SpanContext()
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&OtelSpanContextReturn{
		SpanId:     sc.SpanID().String(),
		TraceId:    sc.TraceID().String(),
		TraceFlags: sc.TraceFlags().String(),
		TraceState: sc.TraceState().String(),
		Remote:     sc.IsRemote(),
	}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *apmClientServer) otelAddEventHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelAddEventArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		http.Error(w, fmt.Sprintf("OtelSetStatus call failed, span with id=%d not found", args.SpanId), http.StatusBadRequest)
		return
	}
	span := sctx.span
	opts := []otel_trace.EventOption{}
	if args.Timestamp != nil {
		// args.Timestamp is represented in microseconds
		opts = append(opts, otel_trace.WithTimestamp(time.UnixMicro(*args.Timestamp)))
	}
	if args.GetAttributes() != nil {
		opts = append(opts, otel_trace.WithAttributes(args.Attributes.ConvertToAttributes()...))
	}
	span.AddEvent(args.Name, opts...)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) otelSetStatusHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelSetStatusArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	sctx, ok := s.otelSpans[args.SpanId]
	if !ok {
		http.Error(w, fmt.Sprintf("OtelSetStatus call failed, span with id=%d not found", args.SpanId), http.StatusBadRequest)
		return
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
		http.Error(w, fmt.Sprintf("OtelSetStatus call failed, status has invalid code %v", args.Code), http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func hex2int(hexStr string) uint64 {
	// remove 0x suffix if found in the input string
	cleaned := strings.Replace(hexStr, "0x", "", -1)
	if len(cleaned) > 16 {
		// truncate 128bit ids to 64bit
		// TODO: revisit this logic, hexStr is expected to be 16 characters long
		cleaned = cleaned[len(cleaned)-16:]
	}
	// base 16 for hexadecimal
	result, err := strconv.ParseUint(cleaned, 16, 64)
	if err != nil {
		fmt.Printf("Converting hex string to uint64 failed, hex string : %s\n", hexStr)
	}
	return result
}
