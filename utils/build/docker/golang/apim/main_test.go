package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

const fixtureRequestID = "request-123"

type calloutStep struct {
	phase     string
	requestID string
	response  string
	assert    func(*testing.T, map[string]json.RawMessage)
}

func TestReplayFixtures(t *testing.T) {
	t.Run("happy-four-call", testHappyFourCallFixture)
	t.Run("block-at-request-headers", testRequestHeadersBlockFixture)
	t.Run("block-at-request-body", testRequestBodyBlockFixture)
}

func testHappyFourCallFixture(t *testing.T) {
	callout := newScriptedCallout(t, []calloutStep{
		{
			phase:     "<RequestHeaders>",
			requestID: "",
			response:  `{"request-id":"request-123","propagate-headers":{"X-Test-Propagated":["yes"]},"allowed-body-size":3}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertGatewayOmitted(t, message)
				assertRequestHeaderAddresses(t, message, nil)
			},
		},
		{
			phase:     "<RequestBody>",
			requestID: fixtureRequestID,
			response:  `{}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertBodyAddresses(t, message, "abc")
			},
		},
		{
			phase:     "<ResponseHeaders>",
			requestID: fixtureRequestID,
			response:  `{"allowed-body-size":8}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertResponseHeaderAddresses(t, message, nil)
			},
		},
		{
			phase:     "<ResponseBody>",
			requestID: fixtureRequestID,
			response:  `{}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertBodyAddresses(t, message, "response")
			},
		},
	})

	var upstreamCalls atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upstreamCalls.Add(1)
		if got := r.Header.Get("X-Test-Propagated"); got != "yes" {
			t.Errorf("propagated header = %q, want yes", got)
		}
		if got := r.Header.Get(bodyModeHeader); got != "" {
			t.Errorf("control header reached upstream as %q", got)
		}
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Errorf("read upstream request body: %v", err)
		}
		if got := string(body); got != "abcdef" {
			t.Errorf("upstream request body = %q, want %q", got, "abcdef")
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Upstream", "yes")
		w.WriteHeader(http.StatusCreated)
		_, _ = io.WriteString(w, "response-body")
	}))
	t.Cleanup(upstream.Close)

	var logs bytes.Buffer
	gateway := newTestGateway(callout.URL, upstream.URL, &logs)
	request := httptest.NewRequest(http.MethodPost, "http://example.test:7777/resource?x=1", strings.NewReader("abcdef"))
	request.RemoteAddr = "198.51.100.4:5678"
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Forwarded-For", "203.0.113.7")
	request.Header.Set(bodyModeHeader, "deferred")

	recorder := httptest.NewRecorder()
	gateway.ServeHTTP(recorder, request)

	if got := recorder.Code; got != http.StatusCreated {
		t.Fatalf("status = %d, want %d", got, http.StatusCreated)
	}
	if got := recorder.Header().Get("X-Upstream"); got != "yes" {
		t.Errorf("upstream response header = %q, want yes", got)
	}
	if got := recorder.Body.String(); got != "response-body" {
		t.Errorf("response body = %q, want %q", got, "response-body")
	}
	if got := upstreamCalls.Load(); got != 1 {
		t.Errorf("upstream calls = %d, want 1", got)
	}
	assertLogLines(t, logs.String(), []string{
		`apim-gateway callout phase=<RequestHeaders> request-id="request-123" path="/resource?x=1" outcome=ok`,
		`apim-gateway callout phase=<RequestBody> request-id="request-123" path="/resource?x=1" outcome=ok`,
		`apim-gateway callout phase=<ResponseHeaders> request-id="request-123" path="/resource?x=1" outcome=ok`,
		`apim-gateway callout phase=<ResponseBody> request-id="request-123" path="/resource?x=1" outcome=ok`,
	})
}

func testRequestHeadersBlockFixture(t *testing.T) {
	callout := newScriptedCallout(t, []calloutStep{{
		phase:     "<RequestHeaders>",
		requestID: "",
		response:  `{"block":{"status":403,"headers":{"X-Block":["headers"]},"content":"YmxvY2tlZC1hdC1oZWFkZXJz"}}`,
		assert: func(t *testing.T, message map[string]json.RawMessage) {
			assertGatewayOmitted(t, message)
			assertRequestHeaderAddresses(t, message, nil)
		},
	}})

	var upstreamCalls atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		upstreamCalls.Add(1)
	}))
	t.Cleanup(upstream.Close)

	gateway := newTestGateway(callout.URL, upstream.URL, io.Discard)
	recorder := httptest.NewRecorder()
	gateway.ServeHTTP(recorder, newFixtureRequest(http.MethodPost, nil))

	assertBlockResponse(t, recorder, http.StatusForbidden, "headers", "blocked-at-headers")
	if got := upstreamCalls.Load(); got != 0 {
		t.Errorf("upstream calls = %d, want 0", got)
	}
}

func testRequestBodyBlockFixture(t *testing.T) {
	callout := newScriptedCallout(t, []calloutStep{
		{
			phase:     "<RequestHeaders>",
			requestID: "",
			response:  `{"request-id":"request-123","allowed-body-size":1024}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertRequestHeaderAddresses(t, message, nil)
			},
		},
		{
			phase:     "<RequestBody>",
			requestID: fixtureRequestID,
			response:  `{"block":{"status":406,"headers":{"X-Block":["body"]},"content":"YmxvY2tlZC1hdC1ib2R5"}}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertBodyAddresses(t, message, "payload")
			},
		},
	})

	var upstreamCalls atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		upstreamCalls.Add(1)
	}))
	t.Cleanup(upstream.Close)

	gateway := newTestGateway(callout.URL, upstream.URL, io.Discard)
	recorder := httptest.NewRecorder()
	gateway.ServeHTTP(recorder, newFixtureRequest(http.MethodPost, strings.NewReader("payload")))

	assertBlockResponse(t, recorder, http.StatusNotAcceptable, "body", "blocked-at-body")
	if got := upstreamCalls.Load(); got != 0 {
		t.Errorf("upstream calls = %d, want 0", got)
	}
}

func TestResponsePhaseBlocksDiscardUpstreamResponse(t *testing.T) {
	for _, fixture := range []struct {
		name       string
		wantStatus int
		steps      []calloutStep
	}{
		{
			name:       "response-headers",
			wantStatus: 451,
			steps: []calloutStep{
				{phase: "<RequestHeaders>", response: `{"request-id":"request-123"}`},
				{phase: "<ResponseHeaders>", requestID: fixtureRequestID, response: `{"block":{"status":451,"headers":{"X-Block":["response-headers"]},"content":"YmxvY2tlZA=="}}`},
			},
		},
		{
			name:       "response-body",
			wantStatus: 452,
			steps: []calloutStep{
				{phase: "<RequestHeaders>", response: `{"request-id":"request-123"}`},
				{phase: "<ResponseHeaders>", requestID: fixtureRequestID, response: `{"allowed-body-size":1024}`},
				{phase: "<ResponseBody>", requestID: fixtureRequestID, response: `{"block":{"status":452,"headers":{"X-Block":["response-body"]},"content":"YmxvY2tlZA=="}}`},
			},
		},
	} {
		t.Run(fixture.name, func(t *testing.T) {
			callout := newScriptedCallout(t, fixture.steps)
			var upstreamCalls atomic.Int32
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
				upstreamCalls.Add(1)
				w.WriteHeader(http.StatusCreated)
				_, _ = io.WriteString(w, "upstream-response")
			}))
			t.Cleanup(upstream.Close)

			gateway := newTestGateway(callout.URL, upstream.URL, io.Discard)
			recorder := httptest.NewRecorder()
			gateway.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "http://example.test:7777/", nil))

			assertBlockResponse(t, recorder, fixture.wantStatus, fixture.name, "blocked")
			if got := upstreamCalls.Load(); got != 1 {
				t.Errorf("upstream calls = %d, want 1", got)
			}
		})
	}
}

func TestInlineBodyModeUsesTwoCallouts(t *testing.T) {
	requestBody := "request-body"
	responseBody := "response-body"
	callout := newScriptedCallout(t, []calloutStep{
		{
			phase:     "<RequestHeaders>",
			requestID: "",
			response:  `{"request-id":"request-123"}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertRequestHeaderAddresses(t, message, &requestBody)
			},
		},
		{
			phase:     "<ResponseHeaders>",
			requestID: fixtureRequestID,
			response:  `{}`,
			assert: func(t *testing.T, message map[string]json.RawMessage) {
				assertResponseHeaderAddresses(t, message, &responseBody)
			},
		},
	})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get(bodyModeHeader); got != "" {
			t.Errorf("control header reached upstream as %q", got)
		}
		w.Header().Set("Content-Type", "text/plain")
		_, _ = io.WriteString(w, responseBody)
	}))
	t.Cleanup(upstream.Close)

	var logs bytes.Buffer
	gateway := newTestGateway(callout.URL, upstream.URL, &logs)
	request := newFixtureRequest(http.MethodPost, strings.NewReader(requestBody))
	request.Header.Set(bodyModeHeader, "inline")
	recorder := httptest.NewRecorder()
	gateway.ServeHTTP(recorder, request)

	if got := recorder.Code; got != http.StatusOK {
		t.Fatalf("status = %d, want %d", got, http.StatusOK)
	}
	assertLogLines(t, logs.String(), []string{
		`apim-gateway callout phase=<RequestHeaders> request-id="request-123" path="/resource?x=1" outcome=ok`,
		`apim-gateway callout phase=<ResponseHeaders> request-id="request-123" path="/resource?x=1" outcome=ok`,
	})
}

func TestFailClosedWhenCalloutPortIsClosed(t *testing.T) {
	var upstreamCalls atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		upstreamCalls.Add(1)
	}))
	t.Cleanup(upstream.Close)

	var logs bytes.Buffer
	gateway := newTestGateway(closedListenerAddress(t), upstream.URL, &logs)
	recorder := httptest.NewRecorder()
	gateway.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "http://example.test:7777/", nil))

	if got := recorder.Code; got != http.StatusBadGateway {
		t.Fatalf("status = %d, want %d", got, http.StatusBadGateway)
	}
	if got := upstreamCalls.Load(); got != 0 {
		t.Errorf("upstream calls = %d, want 0", got)
	}
	// Exactly one line: logCallout reports the callout failure, and failing closed must not
	// duplicate it.
	assertLogPrefixes(t, logs.String(), []string{
		`apim-gateway callout phase=<RequestHeaders> request-id="" path="/" outcome=error`,
	})
}

func TestFailClosedWhenUpstreamPortIsClosed(t *testing.T) {
	callout := newScriptedCallout(t, []calloutStep{{
		phase:     "<RequestHeaders>",
		requestID: "",
		response:  `{"request-id":"request-123"}`,
	}})

	var logs bytes.Buffer
	gateway := newTestGateway(callout.URL, closedListenerAddress(t), &logs)
	recorder := httptest.NewRecorder()
	gateway.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "http://example.test:7777/", nil))

	if got := recorder.Code; got != http.StatusBadGateway {
		t.Fatalf("status = %d, want %d", got, http.StatusBadGateway)
	}
	// The callout succeeded, so the upstream stage was reached and is what failed.
	assertLogPrefixes(t, logs.String(), []string{
		`apim-gateway callout phase=<RequestHeaders> request-id="request-123" path="/" outcome=ok`,
		`apim-gateway fail-closed stage=call-upstream error="`,
	})
}

func TestFailClosedOnMalformedBlock(t *testing.T) {
	for _, fixture := range []struct {
		name       string
		response   string
		wantLogged string
	}{
		{
			name:       "undecodable-content",
			response:   `{"block":{"status":403,"headers":{"X-Block":["headers"]},"content":"!!!"}}`,
			wantLogged: `apim-gateway fail-closed stage=write-block-request-headers error="illegal base64 data`,
		},
		{
			name:       "out-of-range-status",
			response:   `{"block":{"status":42,"headers":{"X-Block":["headers"]},"content":"YmxvY2tlZA=="}}`,
			wantLogged: `apim-gateway fail-closed stage=write-block-request-headers error="invalid block status 42"`,
		},
	} {
		t.Run(fixture.name, func(t *testing.T) {
			callout := newScriptedCallout(t, []calloutStep{{
				phase:     "<RequestHeaders>",
				requestID: "",
				response:  fixture.response,
			}})

			var upstreamCalls atomic.Int32
			upstream := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
				upstreamCalls.Add(1)
			}))
			t.Cleanup(upstream.Close)

			var logs bytes.Buffer
			gateway := newTestGateway(callout.URL, upstream.URL, &logs)
			recorder := httptest.NewRecorder()
			gateway.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "http://example.test:7777/", nil))

			if got := recorder.Code; got != http.StatusBadGateway {
				t.Fatalf("status = %d, want %d", got, http.StatusBadGateway)
			}
			if got := recorder.Header().Get("X-Block"); got != "" {
				t.Errorf("X-Block = %q, want no block header on a fail-closed response", got)
			}
			if got := upstreamCalls.Load(); got != 0 {
				t.Errorf("upstream calls = %d, want 0", got)
			}
			assertLogPrefixes(t, logs.String(), []string{
				`apim-gateway callout phase=<RequestHeaders> request-id="" path="/" outcome=ok`,
				fixture.wantLogged,
			})
		})
	}
}

func closedListenerAddress(t *testing.T) string {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	address := "http://" + listener.Addr().String()
	if err := listener.Close(); err != nil {
		t.Fatal(err)
	}
	return address
}

func newTestGateway(calloutURL, upstreamURL string, stderr io.Writer) *gateway {
	gateway := newGateway()
	gateway.calloutURL = calloutURL
	gateway.upstreamURL = upstreamURL
	gateway.stderr = stderr
	return gateway
}

func newFixtureRequest(method string, body io.Reader) *http.Request {
	request := httptest.NewRequest(method, "http://example.test:7777/resource?x=1", body)
	request.RemoteAddr = "198.51.100.4:5678"
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Forwarded-For", "203.0.113.7")
	return request
}

func newScriptedCallout(t *testing.T, steps []calloutStep) *httptest.Server {
	t.Helper()
	var next int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("callout method = %s, want POST", r.Method)
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		if next >= len(steps) {
			t.Errorf("unexpected extra callout request")
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		step := steps[next]
		next++

		var message map[string]json.RawMessage
		if err := json.NewDecoder(r.Body).Decode(&message); err != nil {
			t.Errorf("decode callout request: %v", err)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		assertRawString(t, message, "phase", step.phase)
		if step.requestID == "" {
			if _, ok := message["request-id"]; ok {
				t.Errorf("phase %s unexpectedly sent request-id", step.phase)
			}
		} else {
			assertRawString(t, message, "request-id", step.requestID)
		}
		if step.assert != nil {
			step.assert(t, message)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, step.response)
	}))
	t.Cleanup(func() {
		server.Close()
		if next != len(steps) {
			t.Errorf("callout calls = %d, want %d", next, len(steps))
		}
	})
	return server
}

func assertGatewayOmitted(t *testing.T, message map[string]json.RawMessage) {
	t.Helper()
	if _, ok := message["gateway"]; ok {
		t.Error("callout request included gateway")
	}
}

func assertRequestHeaderAddresses(t *testing.T, message map[string]json.RawMessage, body *string) {
	t.Helper()
	addresses := decodeAddresses(t, message)
	assertRawString(t, addresses, "method", http.MethodPost)
	assertRawString(t, addresses, "scheme", "http")
	assertRawString(t, addresses, "authority", "example.test:7777")
	assertRawString(t, addresses, "path", "/resource?x=1")
	assertRawString(t, addresses, "remote_addr", "198.51.100.4:5678")

	var headers map[string][]string
	if err := json.Unmarshal(addresses["headers"], &headers); err != nil {
		t.Fatalf("decode request headers: %v", err)
	}
	if got := headers[bodyModeHeader]; len(got) != 0 {
		t.Errorf("control header included in callout addresses: %v", got)
	}
	if got := headers["X-Forwarded-For"]; len(got) != 1 || got[0] != "203.0.113.7" {
		t.Errorf("forwarding header = %v, want [203.0.113.7]", got)
	}
	assertAddressBody(t, addresses, body)
}

func assertResponseHeaderAddresses(t *testing.T, message map[string]json.RawMessage, body *string) {
	t.Helper()
	addresses := decodeAddresses(t, message)
	var status int
	if err := json.Unmarshal(addresses["status_code"], &status); err != nil {
		t.Fatalf("decode response status: %v", err)
	}
	if status != http.StatusCreated && status != http.StatusOK {
		t.Errorf("response status = %d, want 201 or 200", status)
	}
	assertAddressBody(t, addresses, body)
}

func assertBodyAddresses(t *testing.T, message map[string]json.RawMessage, want string) {
	t.Helper()
	assertAddressBody(t, decodeAddresses(t, message), &want)
}

func assertAddressBody(t *testing.T, addresses map[string]json.RawMessage, want *string) {
	t.Helper()
	raw, ok := addresses["body"]
	if want == nil {
		if ok {
			t.Errorf("body = %s, want omitted", raw)
		}
		return
	}
	if !ok {
		t.Fatal("body missing")
	}
	var encoded string
	if err := json.Unmarshal(raw, &encoded); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	decoded, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		t.Fatalf("decode body base64: %v", err)
	}
	if got := string(decoded); got != *want {
		t.Errorf("body = %q, want %q", got, *want)
	}
}

func decodeAddresses(t *testing.T, message map[string]json.RawMessage) map[string]json.RawMessage {
	t.Helper()
	var addresses map[string]json.RawMessage
	if err := json.Unmarshal(message["addresses"], &addresses); err != nil {
		t.Fatalf("decode addresses: %v", err)
	}
	return addresses
}

func assertRawString(t *testing.T, values map[string]json.RawMessage, key, want string) {
	t.Helper()
	raw, ok := values[key]
	if !ok {
		t.Errorf("missing %q", key)
		return
	}
	var got string
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Errorf("decode %q: %v", key, err)
		return
	}
	if got != want {
		t.Errorf("%s = %q, want %q", key, got, want)
	}
}

func assertBlockResponse(t *testing.T, recorder *httptest.ResponseRecorder, wantStatus int, wantHeader, wantBody string) {
	t.Helper()
	if got := recorder.Code; got != wantStatus {
		t.Errorf("status = %d, want %d", got, wantStatus)
	}
	if got := recorder.Header().Get("X-Block"); got != wantHeader {
		t.Errorf("X-Block = %q, want %q", got, wantHeader)
	}
	if got := recorder.Body.String(); got != wantBody {
		t.Errorf("body = %q, want %q", got, wantBody)
	}
}

func assertLogLines(t *testing.T, logs string, want []string) {
	t.Helper()
	got := splitLogLines(logs)
	if len(got) != len(want) {
		t.Fatalf("log lines = %q, want %q", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("log line %d = %q, want %q", i, got[i], want[i])
		}
	}
}

// assertLogPrefixes is assertLogLines for records whose tail carries a platform-dependent
// error string. The line count is still exact.
func assertLogPrefixes(t *testing.T, logs string, want []string) {
	t.Helper()
	got := splitLogLines(logs)
	if len(got) != len(want) {
		t.Fatalf("log lines = %q, want %d lines starting with %q", got, len(want), want)
	}
	for i := range want {
		if !strings.HasPrefix(got[i], want[i]) {
			t.Errorf("log line %d = %q, want prefix %q", i, got[i], want[i])
		}
	}
}

func splitLogLines(logs string) []string {
	return strings.FieldsFunc(strings.TrimSpace(logs), func(r rune) bool { return r == '\n' })
}
