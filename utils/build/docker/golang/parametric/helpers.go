package main

import (
	"encoding/json"
	"fmt"
	"math"
	"strings"

	"go.opentelemetry.io/otel/attribute"
)

type GetTraceConfigReturn struct {
	Config map[string]string `json:"config"`
}

type StartSpanArgs struct {
	Name      string     `json:"name,omitempty"`
	Service   string     `json:"service,omitempty"`
	ParentId  uint64     `json:"parent_id,omitempty"`
	Resource  string     `json:"resource,omitempty"`
	Type      string     `json:"type,omitempty"`
	SpanTags  []Tuple    `json:"span_tags,omitempty"`
	SpanLinks []SpanLink `json:"span_links,omitempty"`
}

type Tuple []string

type SpanLink struct {
	ParentId   uint64           `json:"parent_id"`
	Attributes AttributeKeyVals `json:"attributes,omitempty"`
}

func (x Tuple) Key() string {
	if len(x) == 0 {
		return ""
	}
	return x[0]
}

func (x Tuple) Value() string {
	if len(x) < 2 {
		return ""
	}
	return x[1]
}

type StartSpanReturn struct {
	SpanId  uint64 `json:"span_id"`
	TraceId uint64 `json:"trace_id"`
}

type InjectHeadersArgs struct {
	SpanId uint64 `json:"span_id"`
}

type InjectHeadersReturn struct {
	HttpHeaders []Tuple `json:"http_headers"`
}

type ExtractHeadersArgs struct {
	HttpHeaders []Tuple `json:"http_headers"`
}

type ExtractHeadersReturn struct {
	SpanId *uint64 `json:"span_id"`
}

type FinishSpanArgs struct {
	Id uint64 `json:"span_id"`
}

type SpanSetMetaArgs struct {
	SpanId uint64 `json:"span_id"`
	Key    string `json:"key"`
	Value  string `json:"value"`
}

// InferredValue returns the inferred value of the meta key.
// This is needed because Python and the HTTP API are not typed.
// Some keys have side effects, but only when they are set with
// a value of specific type.
func (ssma SpanSetMetaArgs) InferredValue() interface{} {
	switch ssma.Key {
	// Supported boolean keys
	case "manual.keep", "manual.drop", "analytics.event":
		value := strings.TrimSpace(ssma.Value)
		value = strings.ToLower(value)
		switch value {
		case "true", "1":
			return true
		default:
			return false
		}
	}
	return ssma.Value
}

type SpanSetMetricArgs struct {
	SpanId uint64  `json:"span_id"`
	Key    string  `json:"key"`
	Value  float32 `json:"value"`
}
type SpanSetErrorArgs struct {
	SpanId  uint64 `json:"span_id"`
	Type    string `json:"type"`
	Message string `json:"message"`
	Stack   string `json:"stack"`
}

type SpanRecordExceptionArgs struct {
	SpanId     uint64           `json:"span_id"`
	Message    string           `json:"message"`
	Attributes AttributeKeyVals `json:"attributes"`
}

type SpanRecordExceptionReturn struct {
	ExceptionType string `json:"exception_type"`
}

type OtelStartSpanArgs struct {
	Name       string           `json:"name"`
	ParentId   *uint64          `json:"parent_id"`
	SpanKind   *uint64          `json:"span_kind"`
	Timestamp  *int64           `json:"timestamp"`
	SpanLinks  []SpanLink       `json:"links"`
	Attributes AttributeKeyVals `json:"attributes"`
}

type OtelStartSpanReturn struct {
	SpanId  uint64 `json:"span_id"`
	TraceId uint64 `json:"trace_id"`
}

type OtelEndSpanArgs struct {
	Id        uint64 `json:"id"`
	Timestamp int64  `json:"timestamp"`
}

type OtelFlushSpansArgs struct {
	Seconds uint32 `json:"seconds"`
}

type OtelFlushSpansReturn struct {
	Success bool `json:"success"`
}

type OtelIsRecordingArgs struct {
	SpanId uint64 `json:"span_id"`
}

type OtelIsRecordingReturn struct {
	IsRecording bool `json:"is_recording"`
}

type OtelSpanContextArgs struct {
	SpanId uint64 `json:"span_id,omitempty"`
}

type OtelSpanContextReturn struct {
	SpanId     string `json:"span_id"`
	TraceId    string `json:"trace_id"`
	TraceFlags string `json:"trace_flags"`
	TraceState string `json:"trace_state"`
	Remote     bool   `json:"remote"`
}

type OtelSetStatusArgs struct {
	SpanId      uint64 `json:"span_id"`
	Code        string `json:"code"`
	Description string `json:"description"`
}

type OtelSetNameArgs struct {
	SpanId uint64 `json:"span_id"`
	Name   string `json:"name"`
}

type OtelSetAttributesArgs struct {
	SpanId     uint64           `json:"span_id"`
	Attributes AttributeKeyVals `json:"attributes"`
}

type OtelAddEventArgs struct {
	SpanId     uint64           `json:"span_id"`
	Name       string           `json:"name"`
	Timestamp  int64            `json:"timestamp"`
	Attributes AttributeKeyVals `json:"attributes"`
}

type AttributeKeyVals map[string]interface{}

func (a AttributeKeyVals) ConvertToAttributes() []attribute.KeyValue {
	var attrs []attribute.KeyValue
	for k, v := range a {
		switch t := v.(type) {
		case bool:
			attrs = append(attrs, attribute.Bool(k, t))
		case int:
			attrs = append(attrs, attribute.Int(k, t))
		case int64:
			attrs = append(attrs, attribute.Int64(k, t))
		case float64:
			// By default, all numbers are converted to float64 when using json.Decode, even numbers that are technically ints. This additional check allows tests like test_otel_set_attribute_remapping_httpresponsestatuscode to pass.
			if i, ok := float64ToInt(t); ok {
				attrs = append(attrs, attribute.Int(k, i))
			} else {
				attrs = append(attrs, attribute.Float64(k, t))
			}
		case string:
			attrs = append(attrs, attribute.String(k, t))
		case []interface{}:
			if len(t) > 0 {
				switch tt := t[0].(type) {
				case bool:
					len := len(t)
					boolSlice := make([]bool, len)
					boolSlice[0] = tt
					for i := 1; i < len; i++ {
						boolSlice[i] = t[i].(bool)
					}
					attrs = append(attrs, attribute.BoolSlice(k, boolSlice))
				case int:
					len := len(t)
					intSlice := make([]int, len)
					intSlice[0] = tt
					for i := 1; i < len; i++ {
						intSlice[i] = t[i].(int)
					}
					attrs = append(attrs, attribute.IntSlice(k, intSlice))
				case int64:
					len := len(t)
					int64Slice := make([]int64, len)
					int64Slice[0] = tt
					for i := 1; i < len; i++ {
						int64Slice[i] = t[i].(int64)
					}
					attrs = append(attrs, attribute.Int64Slice(k, int64Slice))
				case float64:
					len := len(t)
					floatSlice := make([]float64, len)
					floatSlice[0] = tt
					for i := 1; i < len; i++ {
						floatSlice[i] = t[i].(float64)
					}
					attrs = append(attrs, attribute.Float64Slice(k, floatSlice))
				case string:
					len := len(t)
					stringSlice := make([]string, len)
					stringSlice[0] = tt
					for i := 1; i < len; i++ {
						stringSlice[i] = t[i].(string)
					}
					attrs = append(attrs, attribute.StringSlice(k, stringSlice))
				default:
					fmt.Printf("Attribute %v has unsupported type%T; dropping\n", k, v)
				}
			}
		default:
			fmt.Printf("Attribute %v has unsupported type%T; dropping\n", k, v)
		}
	}
	return attrs
}

func (a AttributeKeyVals) ConvertToAttributesStringified() []attribute.KeyValue {
	var attrs []attribute.KeyValue
	for k, v := range a {
		s, err := json.Marshal(v)
		if err != nil {
			fmt.Printf("Error converting attribute to json string: %v\n", err.Error())
			continue
		}
		attrs = append(attrs, attribute.String(k, string(s)))
	}
	return attrs
}

// float64ToInt checks if a float64 can be converted to an int without losing precision. If yes, then the converted int is returned along with true. If not, 0 is returned along with false
func float64ToInt(f float64) (int, bool) {
	if f == math.Floor(f) {
		return int(f), true
	}
	return 0, false
}
