package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	ddotellog "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/log"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"go.opentelemetry.io/otel/log"
	sdklog "go.opentelemetry.io/otel/sdk/log"
)

// logWriteHandler handles the /log/write endpoint for generating OTEL logs
func (s *apmClientServer) logWriteHandler(w http.ResponseWriter, r *http.Request) {
	var args LogWriteArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	err := s.WriteLog(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&LogWriteReturn{Success: true}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// WriteLog generates a log record using the OpenTelemetry Logs API
// dd-trace-go sets up the LoggerProvider when DD_LOGS_OTEL_ENABLED=true via StartIfEnabled()
func (s *apmClientServer) WriteLog(args LogWriteArgs) error {
	// Get the logger provider from dd-trace-go (set up when DD_LOGS_OTEL_ENABLED=true)
	provider := ddotellog.GetGlobalLoggerProvider()
	if provider == nil {
		// OTel logs not enabled - this is expected when DD_LOGS_OTEL_ENABLED is false/unset
		// Just return success without emitting any log
		return nil
	}
	logger := provider.Logger(args.LoggerName)

	// Convert string level to OTEL severity
	severity := convertLogLevel(args.Level)

	// Build the log record
	var record log.Record
	record.SetTimestamp(time.Now())
	record.SetBody(log.StringValue(args.Message))
	record.SetSeverity(severity)
	record.SetSeverityText(args.Level)

	// If a span_id is provided, we need to emit the log within that span's context
	var ctx context.Context
	if args.SpanId != 0 {
		// Check if it's a DD span
		if ddSpan, ok := s.spans[args.SpanId]; ok {
			// Create a context with the DD span active
			ctx = tracer.ContextWithSpan(context.Background(), ddSpan)
		} else if otelSpanCtx, ok := s.otelSpans[args.SpanId]; ok {
			// Use the OTel span's context directly
			ctx = otelSpanCtx.ctx
		} else {
			return fmt.Errorf("span not found for span_id: %d", args.SpanId)
		}
	} else {
		ctx = context.Background()
	}

	// Emit the log record
	logger.Emit(ctx, record)

	// Force flush to ensure the log is exported immediately (tests expect immediate availability)
	// Try to type-assert to SDK LoggerProvider which has ForceFlush
	if sdkProvider, ok := provider.(*sdklog.LoggerProvider); ok {
		flushCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := sdkProvider.ForceFlush(flushCtx); err != nil {
			return fmt.Errorf("failed to flush logs: %w", err)
		}
	}

	return nil
}

// convertLogLevel converts a string log level to OTEL log.Severity
func convertLogLevel(level string) log.Severity {
	switch strings.ToUpper(level) {
	case "DEBUG":
		return log.SeverityDebug
	case "INFO":
		return log.SeverityInfo
	case "WARNING", "WARN":
		return log.SeverityWarn
	case "ERROR":
		return log.SeverityError
	default:
		return log.SeverityInfo
	}
}

// otelLogsFlushHandler handles the /log/otel/flush endpoint
func (s *apmClientServer) otelLogsFlushHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelLogsFlushArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Get the logger provider from dd-trace-go
	loggerProvider := ddotellog.GetGlobalLoggerProvider()
	if loggerProvider == nil {
		// OTel logs not enabled
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(&OtelLogsFlushReturn{
			Success: true,
			Message: "nil (OTel logs not enabled)",
		})
		return
	}
	providerName := fmt.Sprintf("%T", loggerProvider)

	// Try to type-assert to SDK LoggerProvider which has ForceFlush
	if sdkProvider, ok := loggerProvider.(*sdklog.LoggerProvider); ok {
		timeout := time.Duration(args.Seconds) * time.Second
		if timeout == 0 {
			timeout = 5 * time.Second
		}
		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		defer cancel()

		if err := sdkProvider.ForceFlush(ctx); err != nil {
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
			Message: providerName,
		})
		return
	}

	// If we can't type-assert, return success anyway (provider may handle flushing internally)
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&OtelLogsFlushReturn{
		Success: true,
		Message: providerName,
	}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}
