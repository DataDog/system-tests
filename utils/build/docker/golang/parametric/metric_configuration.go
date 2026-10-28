package main

import (
	"encoding/json"
	"log"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/go-logr/logr"
	"github.com/go-logr/stdr"
	"go.opentelemetry.io/otel"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
)

// metricReaderConfiguration captures the reader created by the SDK, after its
// environment and option validation. Configuration telemetry can precede that
// validation and report a value the reader subsequently rejects.
type metricReaderConfiguration struct {
	mu       sync.Mutex
	interval *time.Duration
}

func observeMetricReaderConfiguration() *metricReaderConfiguration {
	configuration := &metricReaderConfiguration{}
	// Preserve the SDK's default error-only stderr logger. Only the structured
	// provider-creation record is additionally consumed by this observer.
	fallback := otelLoggerFallback()
	otel.SetLogger(logr.New(&metricConfigurationLogger{
		LogSink:       fallback.GetSink(),
		configuration: configuration,
	}))
	return configuration
}

func otelLoggerFallback() logr.Logger {
	return stdr.New(log.New(os.Stderr, "", log.LstdFlags|log.Lshortfile))
}

func (c *metricReaderConfiguration) intervalMilliseconds() (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.interval == nil {
		return "", false
	}
	return strconv.FormatInt(c.interval.Milliseconds(), 10), true
}

func (c *metricReaderConfiguration) observe(values []any) {
	for i := 0; i+1 < len(values); i += 2 {
		name, ok := values[i].(string)
		if !ok || name != "Readers" {
			continue
		}
		readers, ok := values[i+1].([]sdkmetric.Reader)
		if !ok || len(readers) != 1 {
			return
		}
		reader, ok := readers[0].(*sdkmetric.PeriodicReader)
		if !ok {
			return
		}
		// MarshalLog is the reader's public diagnostic API. Its payload is not
		// a typed configuration contract: leave the field absent if it changes.
		payload, err := json.Marshal(reader.MarshalLog())
		if err != nil {
			return
		}
		var observed struct {
			Type       string
			Registered bool
			Interval   *time.Duration
		}
		if json.Unmarshal(payload, &observed) != nil || observed.Type != "PeriodicReader" || !observed.Registered || observed.Interval == nil {
			return
		}
		c.mu.Lock()
		// Keep the provider created at app startup, rather than unrelated
		// providers that may be created later by configuration requests.
		if c.interval == nil {
			c.interval = observed.Interval
		}
		c.mu.Unlock()
		return
	}
}

type metricConfigurationLogger struct {
	logr.LogSink
	configuration *metricReaderConfiguration
	values        []any
}

func (l *metricConfigurationLogger) Enabled(level int) bool {
	// The OTel SDK publishes provider creation at verbosity 4.
	return level == 4 || l.LogSink.Enabled(level)
}

func (l *metricConfigurationLogger) Info(level int, message string, values ...any) {
	if level == 4 && message == "MeterProvider created" {
		allValues := append(append([]any(nil), l.values...), values...)
		l.configuration.observe(allValues)
	}
	if l.LogSink.Enabled(level) {
		l.LogSink.Info(level, message, values...)
	}
}

func (l *metricConfigurationLogger) WithValues(values ...any) logr.LogSink {
	return &metricConfigurationLogger{
		LogSink:       l.LogSink.WithValues(values...),
		configuration: l.configuration,
		values:        append(append([]any(nil), l.values...), values...),
	}
}

func (l *metricConfigurationLogger) WithName(name string) logr.LogSink {
	return &metricConfigurationLogger{
		LogSink:       l.LogSink.WithName(name),
		configuration: l.configuration,
		values:        l.values,
	}
}
