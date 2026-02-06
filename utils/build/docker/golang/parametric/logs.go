package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	ddotellog "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/log"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"go.opentelemetry.io/otel/attribute"
	otellog "go.opentelemetry.io/otel/log"
)

// otelLoggerCreateHandler handles the /otel/logger/create endpoint
func (s *apmClientServer) otelLoggerCreateHandler(w http.ResponseWriter, r *http.Request) {
	var args LogCreateLoggerArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Check if logger already exists
	if _, exists := s.loggers[args.Name]; exists {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(&LogCreateLoggerReturn{Success: false})
		return
	}

	// Get the logger provider
	provider := ddotellog.GetGlobalLoggerProvider()
	if provider == nil {
		// OTel logs not enabled - just return success without creating logger
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(&LogCreateLoggerReturn{Success: true})
		return
	}

	// Build logger options
	var opts []otellog.LoggerOption
	if args.Version != nil {
		opts = append(opts, otellog.WithInstrumentationVersion(*args.Version))
	}
	if args.SchemaURL != nil {
		opts = append(opts, otellog.WithSchemaURL(*args.SchemaURL))
	}
	if len(args.Attributes) > 0 {
		attrs := make([]attribute.KeyValue, 0, len(args.Attributes))
		for k, v := range args.Attributes {
			// Convert attribute values to appropriate types
			switch val := v.(type) {
			case string:
				attrs = append(attrs, attribute.String(k, val))
			case int:
				attrs = append(attrs, attribute.Int(k, val))
			case int64:
				attrs = append(attrs, attribute.Int64(k, val))
			case float64:
				attrs = append(attrs, attribute.Float64(k, val))
			case bool:
				attrs = append(attrs, attribute.Bool(k, val))
			}
		}
		if len(attrs) > 0 {
			opts = append(opts, otellog.WithInstrumentationAttributes(attrs...))
		}
	}

	// Create logger instance ONCE with all options
	logger := provider.Logger(args.Name, opts...)

	// Store the logger instance for reuse
	s.loggers[args.Name] = logger

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&LogCreateLoggerReturn{Success: true}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// otelLoggerWriteHandler handles the /otel/logger/write endpoint
func (s *apmClientServer) otelLoggerWriteHandler(w http.ResponseWriter, r *http.Request) {
	var args LogGenerateArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Check if OTel logs are enabled
	provider := ddotellog.GetGlobalLoggerProvider()
	if provider == nil {
		// OTel logs not enabled - return success without emitting log
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(&LogGenerateReturn{Success: true})
		return
	}

	// Check if logger exists in registry
	logger, exists := s.loggers[args.LoggerName]
	if !exists {
		http.Error(w, fmt.Sprintf("Logger %s not found in registered loggers", args.LoggerName), http.StatusBadRequest)
		return
	}

	err := s.writeLog(args, logger)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&LogGenerateReturn{Success: true}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// writeLog generates a log record using the OpenTelemetry Logs API
// Uses the pre-created logger instance with its scope metadata
func (s *apmClientServer) writeLog(args LogGenerateArgs, logger otellog.Logger) error {

	// Map severity text to OTel severity number
	var severity otellog.Severity
	switch args.Level {
	case "DEBUG":
		severity = otellog.SeverityDebug
	case "INFO":
		severity = otellog.SeverityInfo
	case "WARN":
		severity = otellog.SeverityWarn
	case "ERROR":
		severity = otellog.SeverityError
	default:
		severity = otellog.SeverityInfo
	}

	// Build the log record
	var record otellog.Record
	record.SetTimestamp(time.Now())
	record.SetBody(otellog.StringValue(args.Message))
	record.SetSeverity(severity)
	record.SetSeverityText(args.Level)

	// If a span_id is provided, we need to emit the log within that span's context
	var ctx context.Context
	if args.SpanId != nil && *args.SpanId != 0 {
		// Check if it's a DD span
		if ddSpan, ok := s.spans[*args.SpanId]; ok {
			// Create a context with the DD span active
			ctx = tracer.ContextWithSpan(context.Background(), ddSpan)
		} else if otelSpanCtx, ok := s.otelSpans[*args.SpanId]; ok {
			// Use the OTel span's context directly
			ctx = otelSpanCtx.ctx
		} else {
			return fmt.Errorf("span not found for span_id: %d", *args.SpanId)
		}
	} else {
		ctx = context.Background()
	}

	// Emit the log record
	logger.Emit(ctx, record)

	// Force flush to ensure the log is exported immediately (tests expect immediate availability)
	flushCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := ddotellog.ForceFlush(flushCtx); err != nil {
		return fmt.Errorf("failed to flush logs: %w", err)
	}

	return nil
}

// otelLogsFlushHandler handles the /log/otel/flush endpoint
func (s *apmClientServer) otelLogsFlushHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelLogsFlushArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Set timeout for flush operation
	timeout := time.Duration(args.Seconds) * time.Second
	if timeout == 0 {
		timeout = 5 * time.Second
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	// Use package-level ForceFlush function
	if err := ddotellog.ForceFlush(ctx); err != nil {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(&OtelLogsFlushReturn{
			Success: false,
			Message: fmt.Sprintf("Error flushing logs: %v", err),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(&OtelLogsFlushReturn{
		Success: true,
		Message: "flushed",
	})
}
