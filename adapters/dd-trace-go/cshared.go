// c-shared FFI surface over the real dd-trace-go tracer.
//
//	go build -buildmode=c-shared -o libddtracego.dylib .
//
// The Temper suite is compiled to Rust; a hand-written Rust adapter implements
// the generated Tracer trait by calling these exported C functions in-process
// (no RPC / subprocess). Spans are delivered to a real ddapm-test-agent
// (DD_TRACE_AGENT_URL); the Rust side reads them back from the agent.
package main

/*
#include <stdlib.h>
*/
import "C"

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"sync"
	"time"
	"unsafe"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	oteltrace "go.opentelemetry.io/otel/trace"
	ddotel "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/ext"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/tinylib/msgp/msgp"
)

var (
	mu          sync.Mutex
	spans       = map[string]*tracer.Span{}
	ctxs        = map[string]*tracer.SpanContext{}
	otelTracer  oteltrace.Tracer
	otelSpans   = map[string]oteltrace.Span{}
	otelCtxs    = map[string]context.Context{}
	configJSON  string
	syntheticN  int
)

// captures the tracer's resolved config, which dd-trace-go logs as JSON on start.
type cfgLogger struct{}

func (cfgLogger) Log(msg string) {
	if i := strings.Index(msg, "CONFIGURATION "); i >= 0 {
		configJSON = msg[i+len("CONFIGURATION "):]
	}
}

func otelSpanID(s oteltrace.Span) string {
	b := s.SpanContext().SpanID()
	return strconv.FormatUint(binary.BigEndian.Uint64(b[:]), 10)
}

// low-64 decimal of the trace id, matching the DD span id convention + the
// agent-delivered trace_id (so CapturedSpan.traceId lines up).
func otelTraceLow64(s oteltrace.Span) string {
	t := s.SpanContext().TraceID()
	return strconv.FormatUint(binary.BigEndian.Uint64(t[8:16]), 10)
}

var otelKinds = map[string]oteltrace.SpanKind{
	"internal": oteltrace.SpanKindInternal,
	"server":   oteltrace.SpanKindServer,
	"client":   oteltrace.SpanKindClient,
	"producer": oteltrace.SpanKindProducer,
	"consumer": oteltrace.SpanKindConsumer,
}

func gs(p *C.char) string { return C.GoString(p) }

// v2: SpanContext.SpanID() is uint64; TraceIDLower() is the low-64 decimal the
// agent/tests expect (TraceID() now returns a 128-bit hex string).
func spanID(s *tracer.Span) string  { return strconv.FormatUint(s.Context().SpanID(), 10) }
func traceID(s *tracer.Span) string { return strconv.FormatUint(s.Context().TraceIDLower(), 10) }

func parentFor(id string) (*tracer.SpanContext, bool) {
	if id == "" || id == "0" {
		return nil, false
	}
	if s, ok := spans[id]; ok {
		return s.Context(), true
	}
	if c, ok := ctxs[id]; ok {
		return c, true
	}
	// cross-API: a DD child of an OTel-created span
	if octx, ok := otelCtxs[id]; ok {
		if ds, ok2 := tracer.SpanFromContext(octx); ok2 {
			return ds.Context(), true
		}
	}
	return nil, false
}

//export ddgo_init
func ddgo_init() {
	otel.SetTracerProvider(ddotel.NewTracerProvider())
	otelTracer = otel.Tracer("conformance")
	// WithLogger routes the startup CONFIGURATION line to our capturer instead
	// of stderr; that JSON is dd-trace-go's resolved config (for ddgo_config).
	tracer.Start(tracer.WithLogger(cfgLogger{}))
}

// ddgo_config returns dd-trace-go's resolved config mapped to the parametric
// config-endpoint keys, as a JSON object (caller frees).
//
//export ddgo_config
func ddgo_config() *C.char {
	var raw map[string]interface{}
	_ = json.Unmarshal([]byte(configJSON), &raw)
	str := func(k string) string {
		if v, ok := raw[k]; ok && v != nil {
			return fmt.Sprintf("%v", v)
		}
		return ""
	}
	flag := func(k string) string {
		if v, ok := raw[k].(bool); ok {
			return strconv.FormatBool(v)
		}
		return "false"
	}
	out := map[string]string{
		"dd_service":                 str("service"),
		"dd_env":                     str("env"),
		"dd_version":                 str("dd_version"),
		"dd_trace_agent_url":         str("agent_url"),
		"dd_trace_debug":             flag("debug"),
		"dd_runtime_metrics_enabled": flag("runtime_metrics_enabled"),
		"dd_trace_sample_rate":       str("sample_rate"),
		"dd_trace_rate_limit":        str("sample_rate_limit"),
	}
	if tags, ok := raw["tags"].(map[string]interface{}); ok {
		parts := make([]string, 0, len(tags))
		for k, v := range tags {
			parts = append(parts, fmt.Sprintf("%s:%v", k, v))
		}
		out["dd_tags"] = strings.Join(parts, ",")
	}
	b, _ := json.Marshal(out)
	return C.CString(string(b))
}

// ddgo_otel_start_span returns "spanID,traceID" (caller frees).
//
//export ddgo_otel_start_span
func ddgo_otel_start_span(name, parent, kind *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	k := otelKinds[gs(kind)]
	if k == 0 {
		k = oteltrace.SpanKindInternal
	}
	parentCtx := context.Background()
	if pc, ok := otelCtxs[gs(parent)]; ok {
		parentCtx = pc
	} else if ds, ok := spans[gs(parent)]; ok {
		// cross-API: an OTel child of a DD-created span
		parentCtx = tracer.ContextWithSpan(context.Background(), ds)
	}
	ctx, span := otelTracer.Start(parentCtx, gs(name), oteltrace.WithSpanKind(k))
	id := otelSpanID(span)
	otelSpans[id] = span
	otelCtxs[id] = ctx
	return C.CString(id + "," + otelTraceLow64(span))
}

//export ddgo_otel_set_attr
func ddgo_otel_set_attr(id, key, value *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := otelSpans[gs(id)]; ok {
		s.SetAttributes(attribute.String(gs(key), gs(value)))
	}
}

//export ddgo_otel_set_attr_num
func ddgo_otel_set_attr_num(id, key *C.char, value C.double) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := otelSpans[gs(id)]; ok {
		f := float64(value)
		if f == float64(int64(f)) {
			s.SetAttributes(attribute.Int64(gs(key), int64(f)))
		} else {
			s.SetAttributes(attribute.Float64(gs(key), f))
		}
	}
}

//export ddgo_otel_end
func ddgo_otel_end(id *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := otelSpans[gs(id)]; ok {
		s.End()
	}
}

//export ddgo_otel_is_recording
func ddgo_otel_is_recording(id *C.char) C.int {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := otelSpans[gs(id)]; ok && s.IsRecording() {
		return 1
	}
	return 0
}

// ddgo_otel_span_context returns "traceHex32,spanHex16" (caller frees).
//
//export ddgo_otel_span_context
func ddgo_otel_span_context(id *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := otelSpans[gs(id)]; ok {
		sc := s.SpanContext()
		return C.CString(sc.TraceID().String() + "," + sc.SpanID().String())
	}
	return C.CString(",")
}

//export ddgo_otel_set_status
func ddgo_otel_set_status(id, code, desc *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := otelSpans[gs(id)]; ok {
		var c codes.Code
		switch gs(code) {
		case "ok":
			c = codes.Ok
		case "error":
			c = codes.Error
		default:
			c = codes.Unset
		}
		s.SetStatus(c, gs(desc))
	}
}

//export ddgo_stop
func ddgo_stop() {
	tracer.Stop()
}

// eventAttr mirrors the suite's EventAttr: a key, a type-kind tag, and one or
// more string-encoded values (arrays carry >1).
type eventAttr struct {
	Key    string   `json:"key"`
	Kind   string   `json:"kind"`
	Values []string `json:"values"`
}

func mustFloat(s string) float64 { f, _ := strconv.ParseFloat(s, 64); return f }
func mustInt(s string) int64     { i, _ := strconv.ParseInt(s, 10, 64); return i }

// eventAttrToKV converts one typed suite attribute into an OTel attribute
// key-value, matching the type the wire encoder expects. Scalars carry a single
// value; *_arr kinds carry the slice form.
func eventAttrToKV(a eventAttr) (attribute.KeyValue, bool) {
	v := ""
	if len(a.Values) > 0 {
		v = a.Values[0]
	}
	switch a.Kind {
	case "string":
		return attribute.String(a.Key, v), true
	case "bool":
		return attribute.Bool(a.Key, v == "true"), true
	case "int":
		return attribute.Int64(a.Key, mustInt(v)), true
	case "double":
		return attribute.Float64(a.Key, mustFloat(v)), true
	case "str_arr":
		return attribute.StringSlice(a.Key, a.Values), true
	case "int_arr":
		vals := make([]int64, len(a.Values))
		for i, s := range a.Values {
			vals[i] = mustInt(s)
		}
		return attribute.Int64Slice(a.Key, vals), true
	case "bool_arr":
		vals := make([]bool, len(a.Values))
		for i, s := range a.Values {
			vals[i] = s == "true"
		}
		return attribute.BoolSlice(a.Key, vals), true
	case "double_arr":
		vals := make([]float64, len(a.Values))
		for i, s := range a.Values {
			vals[i] = mustFloat(s)
		}
		return attribute.Float64Slice(a.Key, vals), true
	}
	return attribute.KeyValue{}, false
}

// ddgo_otel_add_event records a span event through the OTel bridge (which buffers
// it and flushes to the underlying DD span on End). attrsJSON is a JSON array of
// {key,kind,values} objects. timeMicros is the event timestamp in microseconds.
//
//export ddgo_otel_add_event
func ddgo_otel_add_event(id, name *C.char, timeMicros C.longlong, attrsJSON *C.char) {
	mu.Lock()
	defer mu.Unlock()
	s, ok := otelSpans[gs(id)]
	if !ok {
		return
	}
	var attrs []eventAttr
	_ = json.Unmarshal([]byte(gs(attrsJSON)), &attrs)
	kvs := make([]attribute.KeyValue, 0, len(attrs))
	for _, a := range attrs {
		if kv, ok := eventAttrToKV(a); ok {
			kvs = append(kvs, kv)
		}
	}
	ts := time.Unix(0, int64(timeMicros)*1000)
	s.AddEvent(gs(name), oteltrace.WithAttributes(kvs...), oteltrace.WithTimestamp(ts))
}

// encodeSpanJSON serializes a DD span to the v0.4/v1 msgpack wire form and
// converts it to JSON, so the caller can read the exact on-wire field shapes
// the tracer produces (this is the real library encoder, not a reconstruction).
func encodeSpanJSON(s *tracer.Span) (map[string]json.RawMessage, error) {
	var mp bytes.Buffer
	w := msgp.NewWriter(&mp)
	if err := s.EncodeMsg(w); err != nil {
		return nil, err
	}
	if err := w.Flush(); err != nil {
		return nil, err
	}
	var jb bytes.Buffer
	if _, err := msgp.UnmarshalAsJSON(&jb, mp.Bytes()); err != nil {
		return nil, err
	}
	var out map[string]json.RawMessage
	if err := json.Unmarshal(jb.Bytes(), &out); err != nil {
		return nil, err
	}
	return out, nil
}

// ddgo_wire_span_events_json returns the native (v0.4/v1) `span_events` field of
// a span as JSON, captured from the real msgpack wire encoding. Caller frees.
//
//export ddgo_wire_span_events_json
func ddgo_wire_span_events_json(id *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	s := resolveSpan(gs(id))
	if s == nil {
		return C.CString("")
	}
	m, err := encodeSpanJSON(s)
	if err != nil {
		return C.CString("")
	}
	if ev, ok := m["span_events"]; ok {
		return C.CString(string(ev))
	}
	return C.CString("")
}

// ddgo_wire_span_meta_events_json returns the meta-tag `events` JSON string form
// of a span's events (the fallback used when the agent lacks native span-event
// support). Caller frees.
//
//export ddgo_wire_span_meta_events_json
func ddgo_wire_span_meta_events_json(id *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	s := resolveSpan(gs(id))
	if s == nil {
		return C.CString("")
	}
	m := s.AsMap()
	if ev, ok := m[ext.MapSpanEvents]; ok {
		if str, ok := ev.(string); ok {
			return C.CString(str)
		}
	}
	return C.CString("")
}

// ddgo_start_span returns "spanID,traceID" (caller frees).
//
//export ddgo_start_span
func ddgo_start_span(name, parent, service, resource, typ *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	opts := []tracer.StartSpanOption{}
	if s := gs(service); s != "" {
		opts = append(opts, tracer.ServiceName(s))
	}
	if r := gs(resource); r != "" {
		opts = append(opts, tracer.ResourceName(r))
	}
	if t := gs(typ); t != "" {
		opts = append(opts, tracer.SpanType(t))
	}
	if pc, ok := parentFor(gs(parent)); ok {
		opts = append(opts, tracer.ChildOf(pc))
	}
	s := tracer.StartSpan(gs(name), opts...)
	id := spanID(s)
	spans[id] = s
	return C.CString(id + "," + traceID(s))
}

// resolveSpan finds a live span by id, whether created via the DD or OTel API.
func resolveSpan(id string) *tracer.Span {
	if s, ok := spans[id]; ok {
		return s
	}
	if octx, ok := otelCtxs[id]; ok {
		if ds, ok2 := tracer.SpanFromContext(octx); ok2 {
			return ds
		}
	}
	return nil
}

//export ddgo_set_resource
func ddgo_set_resource(id, value *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s := resolveSpan(gs(id)); s != nil {
		s.SetTag("resource.name", gs(value))
	}
}

//export ddgo_set_baggage
func ddgo_set_baggage(id, key, value *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s := resolveSpan(gs(id)); s != nil {
		s.SetBaggageItem(gs(key), gs(value))
	}
}

// ddgo_get_baggage returns a baggage item (caller frees).
//
//export ddgo_get_baggage
func ddgo_get_baggage(id, key *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	if s := resolveSpan(gs(id)); s != nil {
		return C.CString(s.BaggageItem(gs(key)))
	}
	return C.CString("")
}

// ddgo_get_all_baggage returns all baggage items of a span as a JSON object
// (caller frees). v2 exposes SpanContext.ForeachBaggageItem to iterate them.
//
//export ddgo_get_all_baggage
func ddgo_get_all_baggage(id *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	out := map[string]string{}
	if s := resolveSpan(gs(id)); s != nil {
		s.Context().ForeachBaggageItem(func(k, v string) bool {
			out[k] = v
			return true
		})
	} else if c, ok := ctxs[gs(id)]; ok {
		c.ForeachBaggageItem(func(k, v string) bool {
			out[k] = v
			return true
		})
	}
	b, _ := json.Marshal(out)
	return C.CString(string(b))
}

//export ddgo_finish_span
func ddgo_finish_span(id *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := spans[gs(id)]; ok {
		s.Finish()
	}
}

//export ddgo_set_meta
func ddgo_set_meta(id, key, value *C.char) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := spans[gs(id)]; ok {
		s.SetTag(gs(key), gs(value))
	}
}

//export ddgo_set_metric
func ddgo_set_metric(id, key *C.char, value C.double) {
	mu.Lock()
	defer mu.Unlock()
	if s, ok := spans[gs(id)]; ok {
		s.SetTag(gs(key), float64(value))
	}
}

// ddgo_extract takes headers as JSON [["k","v"],...] and returns the extracted
// parent span id ("0" if none). Caller frees.
//
//export ddgo_extract
func ddgo_extract(headersJSON *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	var pairs [][]string
	_ = json.Unmarshal([]byte(gs(headersJSON)), &pairs)
	carrier := tracer.TextMapCarrier{}
	for _, kv := range pairs {
		if len(kv) == 2 {
			if e, ok := carrier[kv[0]]; ok {
				carrier[kv[0]] = e + "," + kv[1]
			} else {
				carrier[kv[0]] = kv[1]
			}
		}
	}
	c, err := tracer.Extract(carrier)
	if err != nil || c == nil {
		return C.CString("0")
	}
	// v2: a W3C `baggage`-only header (no trace headers) extracts to a
	// baggage-only SpanContext whose SpanID() is 0. Returning "0" would read as
	// "no parent" and drop the inherited baggage, so hand back a synthetic
	// non-zero handle keyed to the extracted context; the following
	// StartSpan(ChildOf(...)) then inherits the baggage (fixes get_all D009).
	id := strconv.FormatUint(c.SpanID(), 10)
	if id == "0" {
		syntheticN++
		id = "x" + strconv.Itoa(syntheticN)
	}
	ctxs[id] = c
	return C.CString(id)
}

// ddgo_inject returns the injected headers of a span as a JSON object. Caller frees.
//
//export ddgo_inject
func ddgo_inject(id *C.char) *C.char {
	mu.Lock()
	defer mu.Unlock()
	out := map[string]string{}
	carrier := tracer.TextMapCarrier{}
	if s, ok := spans[gs(id)]; ok {
		_ = tracer.Inject(s.Context(), carrier)
	} else if c, ok := ctxs[gs(id)]; ok {
		_ = tracer.Inject(c, carrier)
	}
	for k, v := range carrier {
		out[k] = v
	}
	b, _ := json.Marshal(out)
	return C.CString(string(b))
}

//export ddgo_flush
func ddgo_flush() {
	tracer.Flush()
}

//export ddgo_free
func ddgo_free(p *C.char) {
	C.free(unsafe.Pointer(p))
}

func main() {}
