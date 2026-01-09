package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/metric"
)

// Metrics endpoint handlers

func (s *apmClientServer) otelGetMeterHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelGetMeterArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelGetMeter(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelGetMeter(args OtelGetMeterArgs) error {
	// Use the global meter provider configured by dd-trace-go
	// This allows dd-trace-go to configure the meter provider with OTLP exporter
	// based on environment variables (OTEL_EXPORTER_OTLP_ENDPOINT, etc.)
	meterProvider := otel.GetMeterProvider()

	opts := []metric.MeterOption{}
	if args.Version != nil {
		opts = append(opts, metric.WithInstrumentationVersion(*args.Version))
	}
	if args.SchemaUrl != nil {
		opts = append(opts, metric.WithSchemaURL(*args.SchemaUrl))
	}
	if args.Attributes != nil {
		opts = append(opts, metric.WithInstrumentationAttributes(args.Attributes.ConvertToAttributes()...))
	}

	meter := meterProvider.Meter(args.Name, opts...)
	s.meters[args.Name] = meter
	return nil
}

func (s *apmClientServer) otelCreateCounterHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateCounterArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateCounter(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateCounter(args OtelCreateCounterArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	opts := []metric.Int64CounterOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	counter, err := meter.Int64Counter(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create counter: %w", err)
	}

	key := createInstrumentKey(args.MeterName, args.Name, "counter", args.Unit, args.Description)
	s.instruments[key] = counter
	return nil
}

func (s *apmClientServer) otelCounterAddHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCounterAddArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCounterAdd(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCounterAdd(args OtelCounterAddArgs) error {
	key := createInstrumentKey(args.MeterName, args.Name, "counter", args.Unit, args.Description)
	instrument, ok := s.instruments[key]
	if !ok {
		return fmt.Errorf("counter with name %s not found for meter %s", args.Name, args.MeterName)
	}

	counter, ok := instrument.(metric.Int64Counter)
	if !ok {
		return fmt.Errorf("instrument is not a counter")
	}

	// Convert value to int64
	value := int64(args.Value)

	// we ignore negative values
	if value < 0 {
		return nil
	}

	opts := metric.AddOption(metric.WithAttributes(args.Attributes.ConvertToAttributes()...))
	counter.Add(context.Background(), value, opts)
	return nil
}

func (s *apmClientServer) otelCreateUpDownCounterHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateUpDownCounterArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateUpDownCounter(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateUpDownCounter(args OtelCreateUpDownCounterArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	opts := []metric.Int64UpDownCounterOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	upDownCounter, err := meter.Int64UpDownCounter(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create updowncounter: %w", err)
	}

	key := createInstrumentKey(args.MeterName, args.Name, "updowncounter", args.Unit, args.Description)
	s.instruments[key] = upDownCounter
	return nil
}

func (s *apmClientServer) otelUpDownCounterAddHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelUpDownCounterAddArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelUpDownCounterAdd(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelUpDownCounterAdd(args OtelUpDownCounterAddArgs) error {
	key := createInstrumentKey(args.MeterName, args.Name, "updowncounter", args.Unit, args.Description)
	instrument, ok := s.instruments[key]
	if !ok {
		return fmt.Errorf("updowncounter with name %s not found for meter %s", args.Name, args.MeterName)
	}

	upDownCounter, ok := instrument.(metric.Int64UpDownCounter)
	if !ok {
		return fmt.Errorf("instrument is not an updowncounter")
	}

	// Convert value to int64
	value := int64(args.Value)
	opts := metric.AddOption(metric.WithAttributes(args.Attributes.ConvertToAttributes()...))
	upDownCounter.Add(context.Background(), value, opts)
	return nil
}

func (s *apmClientServer) otelCreateGaugeHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateGaugeArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateGauge(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateGauge(args OtelCreateGaugeArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	opts := []metric.Int64GaugeOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	gauge, err := meter.Int64Gauge(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create gauge: %w", err)
	}

	key := createInstrumentKey(args.MeterName, args.Name, "gauge", args.Unit, args.Description)
	s.instruments[key] = gauge
	return nil
}

func (s *apmClientServer) otelGaugeRecordHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelGaugeRecordArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelGaugeRecord(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelGaugeRecord(args OtelGaugeRecordArgs) error {
	key := createInstrumentKey(args.MeterName, args.Name, "gauge", args.Unit, args.Description)
	instrument, ok := s.instruments[key]
	if !ok {
		return fmt.Errorf("gauge with name %s not found for meter %s", args.Name, args.MeterName)
	}

	gauge, ok := instrument.(metric.Int64Gauge)
	if !ok {
		return fmt.Errorf("instrument is not a gauge")
	}

	// Convert value to int64
	value := int64(args.Value)
	opts := metric.RecordOption(metric.WithAttributes(args.Attributes.ConvertToAttributes()...))
	gauge.Record(context.Background(), value, opts)
	return nil
}

func (s *apmClientServer) otelCreateHistogramHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateHistogramArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateHistogram(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateHistogram(args OtelCreateHistogramArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	opts := []metric.Int64HistogramOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	histogram, err := meter.Int64Histogram(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create histogram: %w", err)
	}

	key := createInstrumentKey(args.MeterName, args.Name, "histogram", args.Unit, args.Description)
	s.instruments[key] = histogram
	return nil
}

func (s *apmClientServer) otelHistogramRecordHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelHistogramRecordArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelHistogramRecord(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelHistogramRecord(args OtelHistogramRecordArgs) error {
	key := createInstrumentKey(args.MeterName, args.Name, "histogram", args.Unit, args.Description)
	instrument, ok := s.instruments[key]
	if !ok {
		return fmt.Errorf("histogram with name %s not found for meter %s", args.Name, args.MeterName)
	}

	histogram, ok := instrument.(metric.Int64Histogram)
	if !ok {
		return fmt.Errorf("instrument is not a histogram")
	}

	// Convert value to int64
	value := int64(args.Value)

	// Per OpenTelemetry spec, Histogram.Record() must ignore negative values
	// Histograms only accept non-negative values
	if value < 0 {
		// Silently ignore negative values as per OTel spec
		return nil
	}

	opts := metric.RecordOption(metric.WithAttributes(args.Attributes.ConvertToAttributes()...))
	histogram.Record(context.Background(), value, opts)
	return nil
}

func (s *apmClientServer) otelCreateAsynchronousCounterHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateAsynchronousCounterArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateAsynchronousCounter(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateAsynchronousCounter(args OtelCreateAsynchronousCounterArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	// Check if instrument already exists (case-insensitive via key)
	// The key uses lowercase name, so case-insensitive variants map to the same key
	key := createInstrumentKey(args.MeterName, args.Name, "observable_counter", args.Unit, args.Description)
	if _, exists := s.instruments[key]; exists {
		// Instrument already exists, don't register another callback
		// The OpenTelemetry SDK treats instruments with case-insensitive names as identical
		return nil
	}

	opts := []metric.Int64ObservableCounterOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	// Create the observable counter - pass original name, let SDK handle normalization
	observableCounter, err := meter.Int64ObservableCounter(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create asynchronous counter: %w", err)
	}

	// Create callback function that returns constant value
	value := args.Value
	attributes := args.Attributes
	callback := func(_ context.Context, o metric.Observer) error {
		o.ObserveInt64(observableCounter, int64(value), metric.WithAttributes(attributes.ConvertToAttributes()...))
		return nil
	}

	// Register the callback
	if _, err := meter.RegisterCallback(callback, observableCounter); err != nil {
		return fmt.Errorf("failed to register callback for asynchronous counter: %w", err)
	}

	s.instruments[key] = observableCounter
	return nil
}

func (s *apmClientServer) otelCreateAsynchronousUpDownCounterHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateAsynchronousUpDownCounterArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateAsynchronousUpDownCounter(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateAsynchronousUpDownCounter(args OtelCreateAsynchronousUpDownCounterArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	// Check if instrument already exists (case-insensitive via key)
	key := createInstrumentKey(args.MeterName, args.Name, "observable_updowncounter", args.Unit, args.Description)
	if _, exists := s.instruments[key]; exists {
		// Instrument already exists, don't register another callback
		// The OpenTelemetry SDK treats instruments with case-insensitive names as identical
		return nil
	}

	opts := []metric.Int64ObservableUpDownCounterOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	// Create the observable updowncounter - pass original name, let SDK handle normalization
	observableUpDownCounter, err := meter.Int64ObservableUpDownCounter(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create asynchronous updowncounter: %w", err)
	}

	// Create callback function that returns constant value
	value := args.Value
	attributes := args.Attributes
	callback := func(_ context.Context, o metric.Observer) error {
		o.ObserveInt64(observableUpDownCounter, int64(value), metric.WithAttributes(attributes.ConvertToAttributes()...))
		return nil
	}

	// Register the callback
	if _, err := meter.RegisterCallback(callback, observableUpDownCounter); err != nil {
		return fmt.Errorf("failed to register callback for asynchronous updowncounter: %w", err)
	}

	s.instruments[key] = observableUpDownCounter
	return nil
}

func (s *apmClientServer) otelCreateAsynchronousGaugeHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelCreateAsynchronousGaugeArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := s.OtelCreateAsynchronousGauge(args)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) OtelCreateAsynchronousGauge(args OtelCreateAsynchronousGaugeArgs) error {
	meter, ok := s.meters[args.MeterName]
	if !ok {
		return fmt.Errorf("meter with name %s not found", args.MeterName)
	}

	// Check if instrument already exists (case-insensitive via key)
	key := createInstrumentKey(args.MeterName, args.Name, "observable_gauge", args.Unit, args.Description)
	if _, exists := s.instruments[key]; exists {
		// Instrument already exists, don't register another callback
		// The OpenTelemetry SDK treats instruments with case-insensitive names as identical
		return nil
	}

	opts := []metric.Int64ObservableGaugeOption{}
	if args.Unit != "" {
		opts = append(opts, metric.WithUnit(args.Unit))
	}
	if args.Description != "" {
		opts = append(opts, metric.WithDescription(args.Description))
	}

	// Create the observable gauge - pass original name, let SDK handle normalization
	observableGauge, err := meter.Int64ObservableGauge(args.Name, opts...)
	if err != nil {
		return fmt.Errorf("failed to create asynchronous gauge: %w", err)
	}

	// Create callback function that returns constant value
	value := args.Value
	attributes := args.Attributes
	callback := func(_ context.Context, o metric.Observer) error {
		o.ObserveInt64(observableGauge, int64(value), metric.WithAttributes(attributes.ConvertToAttributes()...))
		return nil
	}

	// Register the callback
	if _, err := meter.RegisterCallback(callback, observableGauge); err != nil {
		return fmt.Errorf("failed to register callback for asynchronous gauge: %w", err)
	}

	s.instruments[key] = observableGauge
	return nil
}

func (s *apmClientServer) otelMetricsForceFlushHandler(w http.ResponseWriter, r *http.Request) {
	var args OtelMetricsForceFlushArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	success := s.OtelMetricsForceFlush()

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(&OtelMetricsForceFlushReturn{Success: success}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *apmClientServer) OtelMetricsForceFlush() bool {
	// Get the global meter provider configured by dd-trace-go
	meterProvider := otel.GetMeterProvider()

	// The SDK MeterProvider has a ForceFlush method
	// We need to type assert to access it
	type flusher interface {
		ForceFlush(context.Context) error
	}

	if f, ok := meterProvider.(flusher); ok {
		ctx := context.Background()
		if err := f.ForceFlush(ctx); err != nil {
			fmt.Printf("Error flushing metrics: %v\n", err)
			return false
		}
		return true
	}

	// If ForceFlush is not available, return false
	// This happens when OpenTelemetry metrics is disabled
	fmt.Printf("MeterProvider does not support ForceFlush\n")
	return false
}

// Helper function to create instrument key
func createInstrumentKey(meterName, name, kind, unit, description string) string {
	return fmt.Sprintf("%s,%s,%s,%s,%s", meterName, strings.ToLower(strings.TrimSpace(name)), kind, unit, description)
}
