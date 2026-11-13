package main

import (
	"context"
	"testing"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
)

func TestMetricConfigurationObservesConstructedReader(t *testing.T) {
	// A conflicting environment value proves the observation comes from the
	// actual reader's public diagnostic data, not an environment echo.
	t.Setenv("OTEL_METRIC_EXPORT_INTERVAL", "9000")
	configuration := observeMetricReaderConfiguration()
	defer otel.SetLogger(otelLoggerFallback())
	exporter, err := otlpmetrichttp.New(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	reader := sdkmetric.NewPeriodicReader(exporter, sdkmetric.WithInterval(1234*time.Millisecond))
	provider := sdkmetric.NewMeterProvider(sdkmetric.WithReader(reader))
	defer provider.Shutdown(context.Background())
	interval, observed := configuration.intervalMilliseconds()
	if !observed || interval != "1234" {
		t.Fatalf("expected constructed reader interval 1234, got %q (observed=%v)", interval, observed)
	}
}

func TestMetricConfigurationLeavesUnavailableObservationAbsent(t *testing.T) {
	configuration := &metricReaderConfiguration{}
	configuration.observe([]any{"Readers", "unexpected diagnostic schema"})
	if interval, observed := configuration.intervalMilliseconds(); observed {
		t.Fatalf("unexpected interval %q without a periodic reader", interval)
	}
}
