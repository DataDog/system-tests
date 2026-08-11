package common

import (
	"encoding/json"
	"encoding/xml"
	"errors"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/ext"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

type DatadogInformations struct {
	Name string `json:"name"`
	Version  string `json:"version"`
}

type HealtchCheck struct {
	Status  string              `json:"status"`
	Library DatadogInformations `json:"library"`
}

func InitDatadog() {
	span := tracer.StartSpan("init.service")
	defer span.Finish()
	span.SetTag("whip", "done")
}

// ManualKeepDrop forces the sampling decision of the trace the request belongs to,
// based on the mandatory `decision` query parameter (either "keep" or "drop"), then calls
// downstream so that tests can assert on the sampling decision that gets propagated.
func ManualKeepDrop(w http.ResponseWriter, r *http.Request) {
	span, ok := tracer.SpanFromContext(r.Context())
	if !ok {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("no active span"))
		return
	}

	switch r.URL.Query().Get("decision") {
	case "keep":
		span.SetTag(ext.ManualKeep, true)
	case "drop":
		span.SetTag(ext.ManualDrop, true)
	default:
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte("decision must be keep or drop"))
		return
	}

	const url = "http://localhost:7777/"
	req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, url, nil)
	// Inject the current span's context into req.Header so the headers are visible after
	// client.Do, which injects into a cloned request.
	tracer.Inject(span.Context(), tracer.HTTPHeadersCarrier(req.Header))

	res, err := httpClient().Do(req)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(err.Error()))
		return
	}
	defer res.Body.Close()

	requestHeaders := make(map[string]string, len(req.Header))
	for key, values := range req.Header {
		requestHeaders[strings.ToLower(key)] = strings.Join(values, ",")
	}

	responseHeaders := make(map[string]string, len(res.Header))
	for key, values := range res.Header {
		responseHeaders[key] = strings.Join(values, ",")
	}

	jsonResponse, err := json.Marshal(struct {
		URL             string            `json:"url"`
		StatusCode      int               `json:"status_code"`
		RequestHeaders  map[string]string `json:"request_headers"`
		ResponseHeaders map[string]string `json:"response_headers"`
	}{URL: url, StatusCode: res.StatusCode, RequestHeaders: requestHeaders, ResponseHeaders: responseHeaders})
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(err.Error()))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(jsonResponse)
}

func ParseBody(r *http.Request) (interface{}, error) {
	var payload interface{}
	data, err := io.ReadAll(r.Body)
	if err != nil {
		return nil, err
	}
	// Try parsing body as JSON data
	if err := json.Unmarshal(data, &payload); err == nil {
		return payload, err
	}

	xmlPayload := struct {
		XMLName xml.Name `xml:"string"`
		Attr    string   `xml:"attack,attr"`
		Content string   `xml:",chardata"`
	}{}
	// Try parsing body as XML data
	if err := xml.Unmarshal(data, &xmlPayload); err == nil {
		return xmlPayload, err
	}
	// Default to parsing body as URL encoded data
	return url.ParseQuery(string(data))
}

func ForceSpanIndexingTags() []tracer.StartSpanOption {
	// These tags simulate a retention filter to index spans, otherwise
	// they will only be available in live search of spans!
	//
	// Instead of adding these tags manually, we could also create a retention filter in each org/account
	// that we want to run these e2e tests to retain single spans (to make them available in normal search).
	return []tracer.StartSpanOption{
		tracer.Tag("_dd.filter.kept", 1),
		tracer.Tag("_dd.filter.id", "system_tests_e2e"),
	}
}

func GetHealtchCheck() (HealtchCheck, error) {
	datadogInformations, err := GetDatadogInformations()

	if err != nil {
		return HealtchCheck{}, err
	}

	return HealtchCheck{
		Status:  "ok",
		Library: datadogInformations,
	}, nil
}

func GetDatadogInformations() (DatadogInformations, error) {

	tracerVersion, err := os.ReadFile("SYSTEM_TESTS_LIBRARY_VERSION")
	if err != nil {
		return DatadogInformations{}, errors.New("Can't get SYSTEM_TESTS_LIBRARY_VERSION")
	}

	return DatadogInformations{
		Name: "golang",
		Version:  string(tracerVersion),
	}, nil
}
