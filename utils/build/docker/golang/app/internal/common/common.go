package common

import (
	"encoding/json"
	"encoding/xml"
	"io"
	"net/http"
	"net/url"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

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
