package main

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"reflect"
	"regexp"
	"strings"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/sirupsen/logrus"
)

func (s *apmClientServer) startSpanHandler(w http.ResponseWriter, r *http.Request) {
	var args StartSpanArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}

	span, err := s.StartSpan(r.Context(), &args)
	if err != nil {
		http.Error(w, "Failed to start span: "+err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")

	tIdBytes := span.Context().TraceIDBytes()
	// convert the lower bits to a uint64
	tId := binary.BigEndian.Uint64(tIdBytes[8:])
	response := StartSpanReturn{
		SpanId:  span.Context().SpanID(),
		TraceId: tId,
	}
	if err := json.NewEncoder(w).Encode(response); err != nil {
		http.Error(w, "Failed to encode response: "+err.Error(), http.StatusInternalServerError)
		return
	}
}

func (s *apmClientServer) StartSpan(ctx context.Context, args *StartSpanArgs) (*tracer.Span, error) {
	var opts []tracer.StartSpanOption
	if p := args.ParentId; p > 0 {
		if span, ok := s.spans[p]; ok {
			opts = append(opts, tracer.ChildOf(span.Context()))
		} else if spanContext, ok := s.spanContexts[p]; ok {
			opts = append(opts, tracer.ChildOf(spanContext))
		} else {
			return nil, fmt.Errorf("parent span not found")
		}
	}
	if r := args.Resource; r != "" {
		opts = append(opts, tracer.ResourceName(r))
	}
	if s := args.Service; s != "" {
		opts = append(opts, tracer.ServiceName(s))
	}
	if t := args.Type; t != "" {
		opts = append(opts, tracer.SpanType(t))
	}
	if len(args.SpanTags) != 0 {
		for _, tag := range args.SpanTags {
			opts = append(opts, tracer.Tag(tag.Key(), tag.Value()))
		}
	}
	span := tracer.StartSpan(args.Name, opts...)
	s.spans[span.Context().SpanID()] = span
	return span, nil
}

func (s *apmClientServer) spanSetMetaHandler(w http.ResponseWriter, r *http.Request) {
	var args SpanSetMetaArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}

	span, exists := s.spans[args.SpanId]
	if !exists {
		http.Error(w, "Span not found", http.StatusNotFound)
		return
	}
	span.SetTag(args.Key, args.InferredValue())

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(struct{}{})
}

func (s *apmClientServer) spanSetMetricHandler(w http.ResponseWriter, r *http.Request) {
	var args SpanSetMetricArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	span, exists := s.spans[args.SpanId]
	if !exists {
		http.Error(w, "Span not found", http.StatusNotFound)
		return
	}

	span.SetTag(args.Key, args.Value)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) finishSpanHandler(w http.ResponseWriter, r *http.Request) {
	var args FinishSpanArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()
	span, exists := s.spans[args.Id]
	if !exists {
		http.Error(w, "Span not found", http.StatusNotFound)
		return
	}
	span.Finish()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) flushSpansHandler(w http.ResponseWriter, r *http.Request) {
	tracer.Flush()
	s.spans = make(map[uint64]*tracer.Span)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) flushStatsHandler(w http.ResponseWriter, r *http.Request) {
	tracer.Flush()
	s.spans = make(map[uint64]*tracer.Span)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
}

func (s *apmClientServer) injectHeadersHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var args InjectHeadersArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	span, exists := s.spans[args.SpanId]
	if !exists {
		http.Error(w, "Span not found", http.StatusNotFound)
		return
	}

	headers := tracer.TextMapCarrier(map[string]string{})
	err := tracer.Inject(span.Context(), headers)
	if err != nil {
		http.Error(w, "Error while injecting headers", http.StatusInternalServerError)
		return
	}

	distr := []Tuple{}
	for k, v := range headers {
		distr = append(distr, []string{k, v})
	}

	response := InjectHeadersReturn{HttpHeaders: distr}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

func (s *apmClientServer) extractHeadersHandler(w http.ResponseWriter, r *http.Request) {
	var args ExtractHeadersArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	headers := map[string]string{}
	for _, headerTuple := range args.HttpHeaders {
		k := headerTuple.Key()
		v := headerTuple.Value()
		if k != "" && v != "" {
			headers[k] = v
		}
	}

	sctx, err := tracer.Extract(tracer.TextMapCarrier(headers))
	response := ExtractHeadersReturn{}
	if err == nil {
		spanID := sctx.SpanID()
		response.SpanId = &spanID
		s.spanContexts[spanID] = sctx
	} else {
		fmt.Printf("No trace context extracted from headers %v. headers: %v, args: %v\n", err, headers, args)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

func (s *apmClientServer) spanSetErrorHandler(w http.ResponseWriter, r *http.Request) {
	var args SpanSetErrorArgs
	if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
		http.Error(w, fmt.Sprintf("Error decoding JSON: %v", err), http.StatusBadRequest)
		return
	}

	span, exists := s.spans[args.SpanId]
	if !exists {
		http.Error(w, "Span not found", http.StatusNotFound)
		return
	}

	// Set the error tags on the span
	span.SetTag("error", true)
	span.SetTag("error.msg", args.Message)
	span.SetTag("error.type", args.Type)
	span.SetTag("error.stack", args.Stack)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
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
	DogstatsdAddr          string            `json:"dogstatsd_address"`
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
		log.Printf("Error unmarshaling JSON: %v\n", err)
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
	if addr := strings.Split(l.globalConfig["DogstatsdAddr"], ":"); len(addr) == 2 {
		config["dd_dogstatsd_host"], config["dd_dogstatsd_port"] = addr[0], addr[1]
	} else if len(addr) == 1 {
		config["dd_dogstatsd_host"], config["dd_dogstatsd_port"] = addr[0], ""
	} else {
		config["dd_dogstatsd_host"], config["dd_dogstatsd_port"] = "", ""
	}
	log.Print("Parsed config: ", config)
	return config
}

func (s *apmClientServer) getTraceConfigHandler(w http.ResponseWriter, r *http.Request) {
	var log = &CustomLogger{Logger: logrus.New(), globalConfig: make(map[string]string)}

	tracer.Start(tracer.WithLogger(log))

	tracerEnabled := "true"
	// If globalConfig is empty, then startup log wasn't generated -- tracer must be disabled
	if len(log.globalConfig) == 0 {
		tracerEnabled = "false"
	}

	// Prepare the response
	response := GetTraceConfigReturn{Config: parseTracerConfig(log, tracerEnabled)}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
