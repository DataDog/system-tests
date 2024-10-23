package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"

	"go.opentelemetry.io/otel"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"

	otel_trace "go.opentelemetry.io/otel/trace"
	ddotel "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
)

type apmClientServer struct {
	spans     map[uint64]tracer.Span
	otelSpans map[uint64]spanContext
	tp        *ddotel.TracerProvider
	tracer    otel_trace.Tracer
}

type spanContext struct {
	span otel_trace.Span
	ctx  context.Context
}

func newServer() *apmClientServer {
	s := &apmClientServer{
		spans:     make(map[uint64]tracer.Span),
		otelSpans: make(map[uint64]spanContext),
	}
	s.tp = ddotel.NewTracerProvider()
	otel.SetTracerProvider(s.tp)
	return s
}

func main() {
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
	http.HandleFunc("/trace/span/start", s.startSpanHandler)
	http.HandleFunc("/trace/span/set_meta", s.spanSetMetaHandler)
	// http.HandleFunc("trace/span/finish", s.finishSpanHandler)
	err = http.ListenAndServe(fmt.Sprintf(":%d", port), nil)
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	log.Printf("server listening at %v", fmt.Sprintf("0.0.0.0:%d", port))
}
