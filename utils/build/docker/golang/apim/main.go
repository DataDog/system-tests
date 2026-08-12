package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const (
	calloutEndpoint  = "http://apim-callout:8080/"
	upstreamEndpoint = "http://http-app:8080"
	bodyModeHeader   = "X-Datadog-Apim-Body-Mode"

	calloutTimeout  = 3 * time.Second
	upstreamTimeout = 10 * time.Second

	phaseRequestHeaders  = "<RequestHeaders>"
	phaseRequestBody     = "<RequestBody>"
	phaseResponseHeaders = "<ResponseHeaders>"
	phaseResponseBody    = "<ResponseBody>"
)

// calloutMessage represents the JSON body sent by the gateway on POST /.
// The Addresses field is phase-dependent and decoded separately.
type calloutMessage struct {
	Addresses json.RawMessage `json:"addresses"`
	Gateway   string          `json:"gateway,omitempty"`
	RequestID string          `json:"request-id,omitempty"`
	Phase     string          `json:"phase,omitempty"`
}

// calloutResult represents the JSON response returned to the gateway.
type calloutResult struct {
	RequestID        string              `json:"request-id,omitempty"`
	PropagateHeaders map[string][]string `json:"propagate-headers,omitempty"`
	AllowedBodySize  *int                `json:"allowed-body-size,omitempty"`
	Block            *blockResult        `json:"block,omitempty"`
}

// blockResult represents a blocking decision sent back to the gateway.
type blockResult struct {
	Status  int                 `json:"status"`
	Headers map[string][]string `json:"headers,omitempty"`
	Content string              `json:"content,omitempty"`
}

// addressesRequestHeaders holds the phase-dependent addresses for the request headers phase.
type addressesRequestHeaders struct {
	Method     string              `json:"method"`
	Scheme     string              `json:"scheme"`
	Authority  string              `json:"authority"`
	Path       string              `json:"path"`
	RemoteAddr string              `json:"remote_addr"`
	Headers    map[string][]string `json:"headers"`
	Body       json.RawMessage     `json:"body,omitempty"`
}

// addressesResponseHeaders holds the phase-dependent addresses for the response headers phase.
type addressesResponseHeaders struct {
	StatusCode int                 `json:"status_code"`
	Headers    map[string][]string `json:"headers"`
	Body       json.RawMessage     `json:"body,omitempty"`
}

// addressesBody holds the phase-dependent addresses for the body phase.
type addressesBody struct {
	Body json.RawMessage `json:"body"`
}

type gateway struct {
	calloutURL     string
	upstreamURL    string
	calloutClient  *http.Client
	upstreamClient *http.Client
	stderr         io.Writer
}

func main() {
	if err := http.ListenAndServe(":80", newGateway()); err != nil {
		fmt.Fprintln(os.Stderr, err)
	}
}

func newGateway() *gateway {
	return &gateway{
		calloutURL:     calloutEndpoint,
		upstreamURL:    upstreamEndpoint,
		calloutClient:  &http.Client{Timeout: calloutTimeout},
		upstreamClient: &http.Client{Timeout: upstreamTimeout},
		stderr:         os.Stderr,
	}
}

func (g *gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	requestBody, err := io.ReadAll(r.Body)
	if err != nil {
		g.failClosed(w)
		return
	}
	defer r.Body.Close()

	inline := r.Header.Get(bodyModeHeader) == "inline"
	r.Header.Del(bodyModeHeader)

	requestAddresses := addressesRequestHeaders{
		Method:     r.Method,
		Scheme:     requestScheme(r),
		Authority:  r.Host,
		Path:       r.URL.RequestURI(),
		RemoteAddr: r.RemoteAddr,
		Headers:    map[string][]string(r.Header.Clone()),
	}
	if inline {
		requestAddresses.Body, err = encodedBody(requestBody, nil)
		if err != nil {
			g.failClosed(w)
			return
		}
	}

	phase1, err := g.callout(phaseRequestHeaders, "", requestAddresses)
	if err != nil {
		g.failClosed(w)
		return
	}
	if phase1.Block != nil {
		if err := writeBlock(w, phase1.Block); err != nil {
			g.failClosed(w)
		}
		return
	}

	requestID := phase1.RequestID
	applyHeaders(r.Header, phase1.PropagateHeaders)
	if phase1.AllowedBodySize != nil {
		body, err := encodedBody(requestBody, phase1.AllowedBodySize)
		if err != nil {
			g.failClosed(w)
			return
		}
		phase2, err := g.callout(phaseRequestBody, requestID, addressesBody{Body: body})
		if err != nil {
			g.failClosed(w)
			return
		}
		if phase2.Block != nil {
			if err := writeBlock(w, phase2.Block); err != nil {
				g.failClosed(w)
			}
			return
		}
	}

	upstreamResponse, err := g.callUpstream(r, requestBody)
	if err != nil {
		g.failClosed(w)
		return
	}
	defer upstreamResponse.Body.Close()

	responseBody, err := io.ReadAll(upstreamResponse.Body)
	if err != nil {
		g.failClosed(w)
		return
	}

	responseAddresses := addressesResponseHeaders{
		StatusCode: upstreamResponse.StatusCode,
		Headers:    map[string][]string(upstreamResponse.Header.Clone()),
	}
	if inline {
		responseAddresses.Body, err = encodedBody(responseBody, nil)
		if err != nil {
			g.failClosed(w)
			return
		}
	}

	phase3, err := g.callout(phaseResponseHeaders, requestID, responseAddresses)
	if err != nil {
		g.failClosed(w)
		return
	}
	if phase3.Block != nil {
		if err := writeBlock(w, phase3.Block); err != nil {
			g.failClosed(w)
		}
		return
	}
	if phase3.AllowedBodySize != nil {
		body, err := encodedBody(responseBody, phase3.AllowedBodySize)
		if err != nil {
			g.failClosed(w)
			return
		}
		phase4, err := g.callout(phaseResponseBody, requestID, addressesBody{Body: body})
		if err != nil {
			g.failClosed(w)
			return
		}
		if phase4.Block != nil {
			if err := writeBlock(w, phase4.Block); err != nil {
				g.failClosed(w)
			}
			return
		}
	}

	writeUpstreamResponse(w, upstreamResponse, responseBody)
}

func requestScheme(r *http.Request) string {
	if r.TLS != nil {
		return "https"
	}
	return "http"
}

func (g *gateway) callout(phase, requestID string, addresses any) (calloutResult, error) {
	addressesJSON, err := json.Marshal(addresses)
	if err != nil {
		g.logCallout(phase, requestID, err)
		return calloutResult{}, err
	}
	payload, err := json.Marshal(calloutMessage{
		Addresses: addressesJSON,
		RequestID: requestID,
		Phase:     phase,
	})
	if err != nil {
		g.logCallout(phase, requestID, err)
		return calloutResult{}, err
	}

	request, err := http.NewRequest(http.MethodPost, g.calloutURL, bytes.NewReader(payload))
	if err != nil {
		g.logCallout(phase, requestID, err)
		return calloutResult{}, err
	}
	request.Header.Set("Content-Type", "application/json")

	response, err := g.calloutClient.Do(request)
	if err != nil {
		g.logCallout(phase, requestID, err)
		return calloutResult{}, err
	}
	defer response.Body.Close()
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		err := fmt.Errorf("callout returned %s", response.Status)
		g.logCallout(phase, requestID, err)
		return calloutResult{}, err
	}

	var result calloutResult
	if err := decodeJSON(response.Body, &result); err != nil {
		g.logCallout(phase, requestID, err)
		return calloutResult{}, err
	}
	if phase == phaseRequestHeaders && result.Block == nil && result.RequestID == "" {
		err := fmt.Errorf("phase 1 callout response has no request-id")
		g.logCallout(phase, result.RequestID, err)
		return calloutResult{}, err
	}

	logRequestID := requestID
	if phase == phaseRequestHeaders {
		logRequestID = result.RequestID
	}
	g.logCallout(phase, logRequestID, nil)
	return result, nil
}

func decodeJSON(body io.Reader, result *calloutResult) error {
	decoder := json.NewDecoder(body)
	if err := decoder.Decode(result); err != nil {
		return err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return fmt.Errorf("callout response contains multiple JSON values")
		}
		return err
	}
	return nil
}

func (g *gateway) callUpstream(r *http.Request, body []byte) (*http.Response, error) {
	request, err := http.NewRequestWithContext(r.Context(), r.Method, g.upstreamURL+r.URL.RequestURI(), bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	request.Header = r.Header.Clone()
	request.Host = r.Host
	return g.upstreamClient.Do(request)
}

func encodedBody(body []byte, limit *int) (json.RawMessage, error) {
	if limit != nil {
		if *limit < 0 {
			return nil, fmt.Errorf("negative allowed-body-size")
		}
		if len(body) > *limit {
			body = body[:*limit]
		}
	}
	return json.Marshal(base64.StdEncoding.EncodeToString(body))
}

func applyHeaders(headers http.Header, additions map[string][]string) {
	for name, values := range additions {
		headers[http.CanonicalHeaderKey(name)] = append([]string(nil), values...)
	}
}

func writeBlock(w http.ResponseWriter, block *blockResult) error {
	content, err := base64.StdEncoding.DecodeString(block.Content)
	if err != nil {
		return err
	}
	if block.Status < http.StatusContinue || block.Status > 999 {
		return fmt.Errorf("invalid block status %d", block.Status)
	}
	for name, values := range block.Headers {
		w.Header()[name] = append([]string(nil), values...)
	}
	w.WriteHeader(block.Status)
	_, err = w.Write(content)
	return err
}

func writeUpstreamResponse(w http.ResponseWriter, response *http.Response, body []byte) {
	for name, values := range response.Header {
		w.Header()[name] = append([]string(nil), values...)
	}
	w.WriteHeader(response.StatusCode)
	_, _ = w.Write(body)
}

func (g *gateway) logCallout(phase, requestID string, err error) {
	if err != nil {
		_, _ = fmt.Fprintf(g.stderr, "apim-gateway callout phase=%s request-id=%q outcome=error error=%q\n", phase, requestID, err.Error())
		return
	}
	_, _ = fmt.Fprintf(g.stderr, "apim-gateway callout phase=%s request-id=%q outcome=ok\n", phase, requestID)
}

// The APIM policy uses ignore-error="true", but this shim deliberately fails closed on
// detectable callout failures so system-tests can exercise the mandatory D3 behavior.
func (g *gateway) failClosed(w http.ResponseWriter) {
	http.Error(w, http.StatusText(http.StatusBadGateway), http.StatusBadGateway)
}
