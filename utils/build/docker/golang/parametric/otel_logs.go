package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	otlog "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/log"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	otellog "go.opentelemetry.io/otel/log"
	"go.opentelemetry.io/otel/log/noop"
)

type otelLogger struct {
	logger otellog.Logger
	level  otellog.Severity
}

type otelCreateLoggerArgs struct {
	Name       string           `json:"name"`
	Level      string           `json:"level"`
	Version    *string          `json:"version"`
	SchemaURL  *string          `json:"schema_url"`
	Attributes AttributeKeyVals `json:"attributes"`
}

type otelWriteLogArgs struct {
	LoggerName string  `json:"logger_name"`
	Level      string  `json:"level"`
	Message    string  `json:"message"`
	SpanID     *uint64 `json:"span_id"`
}

type otelFlushLogsArgs struct {
	Seconds int `json:"seconds"`
}

type otelLogReturn struct {
	Success bool   `json:"success"`
	Message string `json:"message,omitempty"`
}

func logSeverity(level string) (otellog.Severity, error) {
	switch strings.ToUpper(level) {
	case "TRACE":
		return otellog.SeverityTrace, nil
	case "DEBUG":
		return otellog.SeverityDebug, nil
	case "INFO":
		return otellog.SeverityInfo, nil
	case "WARN", "WARNING":
		return otellog.SeverityWarn, nil
	case "ERROR":
		return otellog.SeverityError, nil
	case "FATAL", "CRITICAL":
		return otellog.SeverityFatal, nil
	default:
		return otellog.SeverityUndefined, fmt.Errorf("unknown log level %q", level)
	}
}

func (s *apmClientServer) otelCreateLoggerHandler(w http.ResponseWriter, r *http.Request) {
	var args otelCreateLoggerArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	level, err := logSeverity(args.Level)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if _, exists := s.otelLoggers[args.Name]; exists {
		writeLogResponse(w, otelLogReturn{Success: false})
		return
	}

	provider := otlog.GetGlobalLoggerProvider()
	if provider == nil {
		// Start leaves the provider unset when DD_LOGS_OTEL_ENABLED is false.
		provider = noop.NewLoggerProvider()
	}
	opts := []otellog.LoggerOption{}
	if args.Version != nil {
		opts = append(opts, otellog.WithInstrumentationVersion(*args.Version))
	}
	if args.SchemaURL != nil {
		opts = append(opts, otellog.WithSchemaURL(*args.SchemaURL))
	}
	if args.Attributes != nil {
		opts = append(opts, otellog.WithInstrumentationAttributes(args.Attributes.ConvertToAttributes()...))
	}
	s.otelLoggers[args.Name] = otelLogger{logger: provider.Logger(args.Name, opts...), level: level}
	writeLogResponse(w, otelLogReturn{Success: true})
}

func (s *apmClientServer) otelWriteLogHandler(w http.ResponseWriter, r *http.Request) {
	var args otelWriteLogArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	level, err := logSeverity(args.Level)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	logger, exists := s.otelLoggers[args.LoggerName]
	if !exists {
		http.Error(w, "logger not found", http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	if args.SpanID != nil {
		if span, exists := s.spans[*args.SpanID]; exists {
			ctx = tracer.ContextWithSpan(ctx, span)
		} else if span, exists := s.otelSpans[*args.SpanID]; exists {
			ctx = span.ctx
		} else {
			http.Error(w, "span not found", http.StatusBadRequest)
			return
		}
	}
	if level >= logger.level {
		var record otellog.Record
		record.SetTimestamp(time.Now())
		record.SetSeverity(level)
		record.SetSeverityText(strings.ToUpper(args.Level))
		record.SetBody(otellog.StringValue(args.Message))
		logger.logger.Emit(ctx, record)
	}
	writeLogResponse(w, otelLogReturn{Success: true})
}

func (s *apmClientServer) otelFlushLogsHandler(w http.ResponseWriter, r *http.Request) {
	var args otelFlushLogsArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if args.Seconds <= 0 {
		http.Error(w, "seconds must be positive", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), time.Duration(args.Seconds)*time.Second)
	defer cancel()
	if err := otlog.ForceFlush(ctx); err != nil {
		writeLogResponse(w, otelLogReturn{Success: false, Message: err.Error()})
		return
	}
	writeLogResponse(w, otelLogReturn{Success: true, Message: "Logs flushed"})
}

func writeLogResponse(w http.ResponseWriter, result otelLogReturn) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(result); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}
