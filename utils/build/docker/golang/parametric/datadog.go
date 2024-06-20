package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"regexp"

	"github.com/sirupsen/logrus"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

var globalConfig = make(map[string]string)

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
}

func (l *CustomLogger) Log(logMessage string) {
	re := regexp.MustCompile(`DATADOG TRACER CONFIGURATION (\{.*\})`)
	matches := re.FindStringSubmatch(logMessage)
	if len(matches) < 2 {
		log.Printf("JSON not found in log message")
		return
	}
	jsonStr := matches[1]

	var config map[string]interface{}
	if err := json.Unmarshal([]byte(jsonStr), &config); err != nil {
		log.Printf("Error unmarshaling JSON: %v\n", err)
		return
	}

	stringConfig := make(map[string]string)
	for key, value := range config {
		stringConfig[key] = fmt.Sprintf("%v", value)
	}
	globalConfig = stringConfig
}

func parseTracerConfig(tracerEnabled string) map[string]string {
	config := make(map[string]string)
	config["dd_service"] = globalConfig["service"]
	// config["dd_log_level"] = nil // golang doesn't support DD_LOG_LEVEL, only thing it supports is passing in DEBUG or DD_TRACE_DEBUG to set debug to true
	config["dd_trace_sample_rate"] = globalConfig["sample_rate"]
	config["dd_trace_enabled"] = tracerEnabled
	config["dd_runtime_metrics_enabled"] = globalConfig["runtime_metrics_enabled"]
	config["dd_tags"] = globalConfig["tags"]
	config["dd_trace_propagation_style"] = globalConfig["propagation_style_inject"]
	config["dd_trace_debug"] = globalConfig["debug"]
	// config["dd_trace_otel_enabled"] = nil         // golang doesn't support DD_TRACE_OTEL_ENABLED
	// config["dd_trace_sample_ignore_parent"] = nil // golang doesn't support DD_TRACE_SAMPLE_IGNORE_PARENT
	config["dd_env"] = globalConfig["env"]
	config["dd_version"] = globalConfig["dd_version"]
	log.Print("Parsed config: ", config)
	return config
}

func (s *apmClientServer) GetTraceConfig(ctx context.Context, args *GetTraceConfigArgs) (*GetTraceConfigReturn, error) {
	var log = &CustomLogger{logrus.New()}
	tracer.Start(tracer.WithLogger(log))

	tracerEnabled := "true"
	// if globalConfig is empty, then there were no startup logs generated and thus it means the tracer was disabled
	if len(globalConfig) == 0 {
		tracerEnabled = "false"
	}
	return &GetTraceConfigReturn{Config: parseTracerConfig(tracerEnabled)}, nil
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
