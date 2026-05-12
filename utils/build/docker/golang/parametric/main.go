package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"

	ddotel "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry"
	ddmetric "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/metric"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/metric"
	otel_trace "go.opentelemetry.io/otel/trace"
)

type apmClientServer struct {
	spans        map[uint64]*tracer.Span
	spanContexts map[uint64]*tracer.SpanContext
	otelSpans    map[uint64]spanContext
	tp           *ddotel.TracerProvider
	tracer       otel_trace.Tracer
	ofClient     *of.Client
	ddProvider   of.FeatureProvider
	// OTel Metrics
	mp          metric.MeterProvider
	meters      map[string]metric.Meter
	instruments map[string]interface{} // Can be Counter, UpDownCounter, Gauge, Histogram, or Observable variants
}

type spanContext struct {
	span otel_trace.Span
	ctx  context.Context
}

func newServer() *apmClientServer {
	tp := ddotel.NewTracerProvider()
	otel.SetTracerProvider(tp)

	mp, err := ddmetric.NewMeterProvider()
	if err != nil {
		log.Fatalf("failed to create Datadog OTel MeterProvider: %v", err)
	}
	otel.SetMeterProvider(mp)

	s := &apmClientServer{
		spans:        make(map[uint64]*tracer.Span),
		spanContexts: make(map[uint64]*tracer.SpanContext),
		otelSpans:    make(map[uint64]spanContext),
		tp:           tp,
		mp:           mp,
		meters:       make(map[string]metric.Meter),
		instruments:  make(map[string]interface{}),
	}

	s.ddProvider, err = ddof.NewDatadogProvider(ddof.ProviderConfig{})
	if err != nil {
		log.Fatalf("failed to create Datadog OpenFeature provider: %v", err)
	}

	if err := of.SetProvider(s.ddProvider); err != nil {
		log.Fatalf("failed to set Datadog OpenFeature provider and wait for initialization: %v", err)
	}

	s.ofClient = of.NewClient("system-tests-weblog-client")
	return s
}

func main() {
	flag.String("Darg1", "", "Argument 1")
	flag.Parse()
	defer func() {
		if err := recover(); err != nil {
			log.Print("encountered unexpected panic", err)
		}
	}()
	port, err := strconv.Atoi(os.Getenv("APM_TEST_CLIENT_SERVER_PORT"))
	if err != nil {
		log.Fatalf("failed to convert port to integer: %v", err)
	}
	s := newServer()

	// dd-trace endpoints
	http.HandleFunc("/trace/span/start", s.startSpanHandler)
	http.HandleFunc("/trace/span/flush", s.flushSpansHandler)
	http.HandleFunc("/trace/stats/flush", s.flushStatsHandler)
	http.HandleFunc("/trace/span/set_meta", s.spanSetMetaHandler)
	http.HandleFunc("/trace/span/finish", s.finishSpanHandler)
	http.HandleFunc("/trace/span/set_metric", s.spanSetMetricHandler)
	http.HandleFunc("/trace/span/inject_headers", s.injectHeadersHandler)
	http.HandleFunc("/trace/span/extract_headers", s.extractHeadersHandler)
	http.HandleFunc("/trace/span/error", s.spanSetErrorHandler)
	http.HandleFunc("/trace/config", s.getTraceConfigHandler)
	http.HandleFunc("/trace/span/manual_keep", s.spanManualKeepHandler)
	http.HandleFunc("/trace/span/manual_drop", s.spanManualDropHandler)

	// openfeature endpoints
	http.HandleFunc("/ffe/start", s.ffeStart)
	http.HandleFunc("/ffe/evaluate", s.ffeEval)

	// otel-api endpoints:
	http.HandleFunc("/trace/otel/start_span", s.otelStartSpanHandler)
	http.HandleFunc("/trace/otel/end_span", s.otelEndSpanHandler)
	http.HandleFunc("/trace/otel/set_attributes", s.otelSetAttributesHandler)
	http.HandleFunc("/trace/otel/set_name", s.otelSetNameHandler)
	http.HandleFunc("/trace/otel/flush", s.otelFlushSpansHandler)
	http.HandleFunc("/trace/otel/is_recording", s.otelIsRecordingHandler)
	http.HandleFunc("/trace/otel/span_context", s.otelSpanContextHandler)
	http.HandleFunc("/trace/otel/add_event", s.otelAddEventHandler)
	http.HandleFunc("/trace/otel/set_status", s.otelSetStatusHandler)

	// otel-metrics endpoints:
	http.HandleFunc("/metrics/otel/get_meter", s.otelGetMeterHandler)
	http.HandleFunc("/metrics/otel/create_counter", s.otelCreateCounterHandler)
	http.HandleFunc("/metrics/otel/counter_add", s.otelCounterAddHandler)
	http.HandleFunc("/metrics/otel/create_updowncounter", s.otelCreateUpDownCounterHandler)
	http.HandleFunc("/metrics/otel/updowncounter_add", s.otelUpDownCounterAddHandler)
	http.HandleFunc("/metrics/otel/create_gauge", s.otelCreateGaugeHandler)
	http.HandleFunc("/metrics/otel/gauge_record", s.otelGaugeRecordHandler)
	http.HandleFunc("/metrics/otel/create_histogram", s.otelCreateHistogramHandler)
	http.HandleFunc("/metrics/otel/histogram_record", s.otelHistogramRecordHandler)
	http.HandleFunc("/metrics/otel/create_asynchronous_counter", s.otelCreateAsynchronousCounterHandler)
	http.HandleFunc("/metrics/otel/create_asynchronous_updowncounter", s.otelCreateAsynchronousUpDownCounterHandler)
	http.HandleFunc("/metrics/otel/create_asynchronous_gauge", s.otelCreateAsynchronousGaugeHandler)
	http.HandleFunc("/metrics/otel/force_flush", s.otelMetricsForceFlushHandler)

	err = http.ListenAndServe(fmt.Sprintf(":%d", port), nil)
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	log.Printf("server listening at %v", fmt.Sprintf("0.0.0.0:%d", port))
}
