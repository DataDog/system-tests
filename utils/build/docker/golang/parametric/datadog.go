package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	reflect "reflect"
	"regexp"
	"strings"

	"github.com/sirupsen/logrus"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func (s *apmClientServer) StartSpan(ctx context.Context, args *StartSpanArgs) (*StartSpanReturn, error) {
	var opts []tracer.StartSpanOption
	if args.GetParentId() > 0 {
		parent := s.spans[*args.ParentId]
		opts = append(opts, tracer.ChildOf(parent.Context()))
	}
	if args.Resource != nil {
		opts = append(opts, tracer.ResourceName(*args.Resource))
	}
	if args.Service != nil {
		opts = append(opts, tracer.ServiceName(*args.Service))
	}
	if args.Type != nil {
		opts = append(opts, tracer.SpanType(*args.Type))
	}

	if args.GetSpanTags() != nil && len(args.SpanTags) != 0 {
		for _, tag := range args.SpanTags {
			opts = append(opts, tracer.Tag(tag.GetKey(), tag.GetValue()))
		}
	}

	if args.GetHttpHeaders() != nil && len(args.HttpHeaders.HttpHeaders) != 0 {
		headers := map[string]string{}
		for _, headerTuple := range args.HttpHeaders.HttpHeaders {
			k := headerTuple.GetKey()
			v := headerTuple.GetValue()
			if k != "" && v != "" {
				headers[k] = v
			}
		}

		sctx, err := tracer.Extract(tracer.TextMapCarrier(headers))
		if err != nil {
			fmt.Println("failed in StartSpan", err, headers)
		} else {
			opts = append(opts, tracer.ChildOf(sctx))
		}
	}
	span := tracer.StartSpan(args.Name, opts...)
	if args.GetOrigin() != "" {
		span.SetTag("_dd.origin", *args.Origin)
	}
	s.spans[span.Context().SpanID()] = span
	return &StartSpanReturn{
		SpanId:  span.Context().SpanID(),
		TraceId: span.Context().TraceID(),
	}, nil
}

func (s *apmClientServer) SpanSetMeta(ctx context.Context, args *SpanSetMetaArgs) (*SpanSetMetaReturn, error) {
	span := s.spans[args.SpanId]
	span.SetTag(args.Key, args.Value)
	return &SpanSetMetaReturn{}, nil
}

func (s *apmClientServer) SpanSetMetric(ctx context.Context, args *SpanSetMetricArgs) (*SpanSetMetricReturn, error) {
	span := s.spans[args.SpanId]
	span.SetTag(args.Key, args.Value)
	return &SpanSetMetricReturn{}, nil
}

func (s *apmClientServer) FinishSpan(ctx context.Context, args *FinishSpanArgs) (*FinishSpanReturn, error) {
	span := s.spans[args.Id]
	span.Finish()
	return &FinishSpanReturn{}, nil
}

func (s *apmClientServer) FlushSpans(context.Context, *FlushSpansArgs) (*FlushSpansReturn, error) {
	tracer.Flush()
	s.spans = make(map[uint64]tracer.Span)
	return &FlushSpansReturn{}, nil
}

func (s *apmClientServer) FlushTraceStats(context.Context, *FlushTraceStatsArgs) (*FlushTraceStatsReturn, error) {
	tracer.Flush()
	s.spans = make(map[uint64]tracer.Span)
	return &FlushTraceStatsReturn{}, nil
}

func (s *apmClientServer) StopTracer(context.Context, *StopTracerArgs) (*StopTracerReturn, error) {
	tracer.Stop()
	return &StopTracerReturn{}, nil
}

func (s *apmClientServer) SpanSetError(ctx context.Context, args *SpanSetErrorArgs) (*SpanSetErrorReturn, error) {
	span := s.spans[args.SpanId]
	span.SetTag("error", true)
	span.SetTag("error.msg", args.Message)
	span.SetTag("error.type", args.Type)
	span.SetTag("error.stack", args.Stack)
	return &SpanSetErrorReturn{}, nil
}

type CustomLogger struct {
	*logrus.Logger
	globalConfig map[string]string
}

type Config struct {
	Service                string            `json:"service"`
	SampleRate             string            `json:"sample_rate"`
	RuntimeMetricsEnabled  bool              `json:"runtime_metrics_enabled"`
	Tags                   map[string]string `json:"tags"`
	PropagationStyleInject string            `json:"propagation_style_inject"`
	Debug                  bool              `json:"debug"`
	Env                    string            `json:"env"`
	DdVersion              string            `json:"dd_version"`
	TraceAgentURL          string            `json:"agent_url"`
	RateLimit              string            `json:"sample_rate_limit"`
}

// Log is a custom logger that extracts & parses the JSON configuration from the log message
// This is done to allow for the testing of tracer configuration using the startup logs as it seems
// to be the most simple way to do so
func (l *CustomLogger) Log(logMessage string) {
	re := regexp.MustCompile(`DATADOG TRACER CONFIGURATION (\{.*\})`)
	matches := re.FindStringSubmatch(logMessage)
	if len(matches) < 2 {
		log.Print("JSON not found in log message")
		return
	}
	jsonStr := matches[1]

	var config Config
	if err := json.Unmarshal([]byte(strings.ToLower(jsonStr)), &config); err != nil {
		log.Print("Error unmarshaling JSON: %v\n", err)
		return
	}

	stringConfig := make(map[string]string)

	// Convert the config struct to a map of strings
	val := reflect.ValueOf(config)
	for i := 0; i < val.Type().NumField(); i++ {
		field := val.Type().Field(i)
		valueField := val.Field(i)

		// Convert field value to string and then to lowercase
		stringValue := fmt.Sprintf("%v", valueField.Interface())
		stringConfig[field.Name] = strings.ToLower(stringValue)
	}
	l.globalConfig = stringConfig
}

func parseTracerConfig(l *CustomLogger, tracerEnabled string) map[string]string {
	config := make(map[string]string)
	config["dd_service"] = l.globalConfig["Service"]
	// config["dd_log_level"] = nil // dd-trace-go does not support DD_LOG_LEVEL (use DD_TRACE_DEBUG instead)
	config["dd_trace_sample_rate"] = l.globalConfig["SampleRate"]
	config["dd_trace_enabled"] = tracerEnabled
	config["dd_runtime_metrics_enabled"] = l.globalConfig["RuntimeMetricsEnabled"]
	config["dd_tags"] = l.globalConfig["Tags"]
	config["dd_trace_propagation_style"] = l.globalConfig["PropagationStyleInject"]
	config["dd_trace_debug"] = l.globalConfig["Debug"]
	// config["dd_trace_otel_enabled"] = nil         // golang doesn't support DD_TRACE_OTEL_ENABLED
	// config["dd_trace_sample_ignore_parent"] = nil // golang doesn't support DD_TRACE_SAMPLE_IGNORE_PARENT
	config["dd_env"] = l.globalConfig["Env"]
	config["dd_version"] = l.globalConfig["DdVersion"]
	config["dd_trace_agent_url"] = l.globalConfig["TraceAgentURL"]
	config["dd_trace_rate_limit"] = l.globalConfig["RateLimit"]
	log.Print("Parsed config: ", config)
	return config
}

func (s *apmClientServer) GetTraceConfig(ctx context.Context, args *GetTraceConfigArgs) (*GetTraceConfigReturn, error) {
	var log = &CustomLogger{logrus.New(), make(map[string]string)}
	tracer.Start(tracer.WithLogger(log))

	tracerEnabled := "true"
	// if globalConfig is empty, then there were no startup logs generated and thus it means the tracer was disabled
	if len(log.globalConfig) == 0 {
		tracerEnabled = "false"
	}
	return &GetTraceConfigReturn{Config: parseTracerConfig(log, tracerEnabled)}, nil
}

func (s *apmClientServer) InjectHeaders(ctx context.Context, args *InjectHeadersArgs) (*InjectHeadersReturn, error) {
	span := s.spans[args.SpanId]
	headers := tracer.TextMapCarrier(map[string]string{})
	err := tracer.Inject(span.Context(), headers)
	if err != nil {
		fmt.Println("error while injecting")
	}
	distr := []*HeaderTuple{}
	for k, v := range headers {
		distr = append(distr, &HeaderTuple{Key: k, Value: v})
	}
	return &InjectHeadersReturn{HttpHeaders: &DistributedHTTPHeaders{HttpHeaders: distr}}, nil
}
