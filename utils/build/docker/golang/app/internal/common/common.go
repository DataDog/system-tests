package common

import (
	"encoding/json"
	"encoding/xml"
	"errors"
	"io"
	"net/http"
	"net/url"
	"os"

	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

type DatadogInformations struct {
	Language                string `json:"language"`
	Version                 string `json:"version"`
	AppsecEventRulesVersion string `json:"appsec_event_rules_version"`
	LibddwafVersion         string `json:"libddwaf_version"`
}

type HealtchCheck struct {
	Status  string              `json:"status"`
	Library DatadogInformations `json:"library"`
}

func init() {
	os.Setenv("DD_TRACE_DEBUG", "true")
}

func InitDatadog() {
	span := tracer.StartSpan("init.service")
	defer span.Finish()
	span.SetTag("whip", "done")
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

func ForceSpanIndexingTags() []ddtrace.StartSpanOption {
	// These tags simulate a retention filter to index spans, otherwise
	// they will only be available in live search of spans!
	//
	// Instead of adding these tags manually, we could also create a retention filter in each org/account
	// that we want to run these e2e tests to retain single spans (to make them available in normal search).
	return []ddtrace.StartSpanOption{
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

	appsecRulesVersion, err := os.ReadFile("SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION")
	if err != nil {
		return DatadogInformations{}, errors.New("Can't get SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION")
	}

	return DatadogInformations{
		Language:                "golang",
		Version:                 string(tracerVersion),
		AppsecEventRulesVersion: string(appsecRulesVersion),
	}, nil
}
