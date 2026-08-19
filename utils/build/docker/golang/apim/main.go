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
	bodyModeInline   = "inline"
	bodyModeVerify   = "inline-verify-state"

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
		os.Exit(1)
	}
}

func newGateway() *gateway {
	return &gateway{
		calloutURL:     calloutEndpoint,
		upstreamURL:    upstreamEndpoint,
		calloutClient:  &http.Client{Timeout: calloutTimeout, CheckRedirect: noRedirect},
		upstreamClient: &http.Client{Timeout: upstreamTimeout, CheckRedirect: noRedirect},
		stderr:         os.Stderr,
	}
}

// noRedirect makes a client hand a 3xx back to its caller instead of following it. A gateway must
// forward the upstream's redirect verbatim rather than resolving it (following also rewrites a POST
// into a GET on a 301/302/303), and the callout client must treat a 3xx as the non-2xx it is
// instead of silently following it into an accepted 200.
func noRedirect(*http.Request, []*http.Request) error {
	return http.ErrUseLastResponse
}

func (g *gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	requestBody, err := io.ReadAll(r.Body)
	if err != nil {
		g.failClosed(w, "read-request-body", err)
		return
	}
	defer r.Body.Close()

	requestPath := r.URL.RequestURI()
	bodyMode := r.Header.Get(bodyModeHeader)
	inline := bodyMode == bodyModeInline || bodyMode == bodyModeVerify
	r.Header.Del(bodyModeHeader)

	requestAddresses := addressesRequestHeaders{
		Method:     r.Method,
		Scheme:     requestScheme(r),
		Authority:  r.Host,
		Path:       requestPath,
		RemoteAddr: r.RemoteAddr,
		Headers:    map[string][]string(r.Header.Clone()),
	}
	if inline {
		requestAddresses.Body, err = encodedBody(requestBody, nil)
		if err != nil {
			g.failClosed(w, "encode-inline-request-body", err)
			return
		}
	}

	phase1, err := g.callout(phaseRequestHeaders, "", requestPath, requestAddresses)
	if err != nil {
		g.writeFailClosed(w)
		return
	}
	if phase1.Block != nil {
		if err := writeBlock(w, phase1.Block); err != nil {
			g.failClosed(w, "write-block-request-headers", err)
		}
		return
	}

	requestID := phase1.RequestID
	applyHeaders(r.Header, phase1.PropagateHeaders)
	if phase1.AllowedBodySize != nil {
		body, err := encodedBody(requestBody, phase1.AllowedBodySize)
		if err != nil {
			g.failClosed(w, "encode-request-body", err)
			return
		}
		phase2, err := g.callout(phaseRequestBody, requestID, requestPath, addressesBody{Body: body})
		if err != nil {
			g.writeFailClosed(w)
			return
		}
		if phase2.Block != nil {
			if err := writeBlock(w, phase2.Block); err != nil {
				g.failClosed(w, "write-block-request-body", err)
			}
			return
		}
	}

	upstreamResponse, err := g.callUpstream(r, requestBody)
	if err != nil {
		g.failClosed(w, "call-upstream", err)
		return
	}
	defer upstreamResponse.Body.Close()

	responseBody, err := io.ReadAll(upstreamResponse.Body)
	if err != nil {
		g.failClosed(w, "read-upstream-body", err)
		return
	}

	responseAddresses := addressesResponseHeaders{
		StatusCode: upstreamResponse.StatusCode,
		Headers:    map[string][]string(upstreamResponse.Header.Clone()),
	}
	if inline {
		responseAddresses.Body, err = encodedBody(responseBody, nil)
		if err != nil {
			g.failClosed(w, "encode-inline-response-body", err)
			return
		}
	}

	phase3, err := g.callout(phaseResponseHeaders, requestID, requestPath, responseAddresses)
	if err != nil {
		g.writeFailClosed(w)
		return
	}
	if phase3.Block != nil {
		if err := writeBlock(w, phase3.Block); err != nil {
			g.failClosed(w, "write-block-response-headers", err)
		}
		return
	}
	if bodyMode == bodyModeVerify {
		if _, err := g.callout(phaseResponseHeaders, requestID, requestPath, responseAddresses); err != nil {
			g.writeFailClosed(w)
			return
		}
	}
	if phase3.AllowedBodySize != nil {
		body, err := encodedBody(responseBody, phase3.AllowedBodySize)
		if err != nil {
			g.failClosed(w, "encode-response-body", err)
			return
		}
		phase4, err := g.callout(phaseResponseBody, requestID, requestPath, addressesBody{Body: body})
		if err != nil {
			g.writeFailClosed(w)
			return
		}
		if phase4.Block != nil {
			if err := writeBlock(w, phase4.Block); err != nil {
				g.failClosed(w, "write-block-response-body", err)
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

func (g *gateway) callout(phase, requestID, requestPath string, addresses any) (calloutResult, error) {
	addressesJSON, err := json.Marshal(addresses)
	if err != nil {
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}
	payload, err := json.Marshal(calloutMessage{
		Addresses: addressesJSON,
		RequestID: requestID,
		Phase:     phase,
	})
	if err != nil {
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}

	request, err := http.NewRequest(http.MethodPost, g.calloutURL, bytes.NewReader(payload))
	if err != nil {
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}
	request.Header.Set("Content-Type", "application/json")

	response, err := g.calloutClient.Do(request)
	if err != nil {
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}
	defer response.Body.Close()
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		err := fmt.Errorf("callout returned %s", response.Status)
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}

	var result calloutResult
	// Decode exactly one JSON value and reject trailing data. A bare Decode stops at the end of
	// the first value, so a payload like `{"request-id":"rid"} {"block":{"status":403}}` would
	// decode "fine" and silently drop the block, letting the request reach the upstream (fail
	// open). More() reports whether another value follows, which is the trailing garbage.
	decoder := json.NewDecoder(response.Body)
	if err := decoder.Decode(&result); err != nil {
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}
	if decoder.More() {
		err := fmt.Errorf("callout response has trailing data after the JSON value")
		g.logCallout(phase, requestID, requestPath, err)
		return calloutResult{}, err
	}
	if phase == phaseRequestHeaders && result.Block == nil && result.RequestID == "" {
		err := fmt.Errorf("phase 1 callout response has no request-id")
		g.logCallout(phase, result.RequestID, requestPath, err)
		return calloutResult{}, err
	}

	logRequestID := requestID
	if phase == phaseRequestHeaders {
		logRequestID = result.RequestID
	}
	g.logCallout(phase, logRequestID, requestPath, nil)
	return result, nil
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
	// Reject 1xx as well as out-of-range codes. WriteHeader(1xx) sends an informational response
	// without committing, so a following Write would commit an implicit 200 OK carrying the block
	// body: the client sees 200 and the upstream is never called. The lower bound must be 200.
	if block.Status < http.StatusOK || block.Status > 999 {
		return fmt.Errorf("invalid block status %d", block.Status)
	}
	// canonicalize: a lowercase name from the callout would not be found by Go's internal
	// Header.get, so the server would content-sniff and emit a second Content-Type
	applyHeaders(w.Header(), block.Headers)
	w.WriteHeader(block.Status)
	_, _ = w.Write(content)
	return nil
}

func writeUpstreamResponse(w http.ResponseWriter, response *http.Response, body []byte) {
	for name, values := range response.Header {
		w.Header()[name] = append([]string(nil), values...)
	}
	w.WriteHeader(response.StatusCode)
	_, _ = w.Write(body)
}

func (g *gateway) logCallout(phase, requestID, requestPath string, err error) {
	if err != nil {
		_, _ = fmt.Fprintf(g.stderr, "apim-gateway callout phase=%s request-id=%q path=%q outcome=error error=%q\n", phase, requestID, requestPath, err.Error())
		return
	}
	_, _ = fmt.Fprintf(g.stderr, "apim-gateway callout phase=%s request-id=%q path=%q outcome=ok\n", phase, requestID, requestPath)
}

// The APIM policy uses ignore-error="true", but this shim deliberately fails closed on
// detectable callout failures so system-tests can exercise the mandatory D3 behavior.
// failClosed reports the causing error on stderr, tagged with the stage that failed, then
// returns the fail-closed status.
func (g *gateway) failClosed(w http.ResponseWriter, stage string, err error) {
	_, _ = fmt.Fprintf(g.stderr, "apim-gateway fail-closed stage=%s error=%q\n", stage, err.Error())
	g.writeFailClosed(w)
}

// writeFailClosed returns the fail-closed status for a failure that logCallout has already
// reported, so a callout failure is diagnosed exactly once.
func (g *gateway) writeFailClosed(w http.ResponseWriter) {
	http.Error(w, http.StatusText(http.StatusBadGateway), http.StatusBadGateway)
}
