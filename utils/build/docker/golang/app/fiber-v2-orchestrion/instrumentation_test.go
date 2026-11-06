//go:build orchestrion

package main

import (
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/mocktracer"
)

// Run with orchestrion go test -tags=appsec,orchestrion.
func TestAutomaticFiberInstrumentation(t *testing.T) {
	mt := mocktracer.Start()
	defer mt.Stop()
	app := newApp()

	for _, path := range []string{"/sample_rate_route/1", "/identify", "/returnheaders"} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.Header.Set("User-Agent", "system_tests rid/fiber-instrumentation")
		res, err := app.Test(req, -1)
		if err != nil {
			t.Fatal(err)
		}
		res.Body.Close()
		if res.StatusCode != http.StatusOK {
			t.Fatalf("%s returned %d", path, res.StatusCode)
		}
	}

	spans := mt.FinishedSpans()
	if len(spans) != 3 {
		t.Fatalf("got %d spans, want one Fiber server span per request: %v", len(spans), spans)
	}
	for _, span := range spans {
		if span.Tag("component") != "gofiber/fiber.v2" || span.Tag("span.kind") != "server" {
			t.Fatalf("not a Fiber server span: %v", span.Tags())
		}
		if span.Tag("system_tests.request.user_agent") != "system_tests rid/fiber-instrumentation" {
			t.Fatalf("request correlation tag missing: %v", span.Tags())
		}
	}
	if spans[0].Tag("http.route") != "/sample_rate_route/:i" {
		t.Fatalf("route parameter was not captured: %v", spans[0].Tags())
	}
	if spans[1].Tag("usr.id") != "usr.id" {
		t.Fatalf("SDK did not receive the Fiber span: %v", spans[1].Tags())
	}
}

// Orchestrion also instruments the client. Count server and client spans separately.
func TestAutomaticFiberListenerInstrumentation(t *testing.T) {
	mt := mocktracer.Start()
	defer mt.Stop()
	app := newApp()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	served := make(chan error, 1)
	go func() { served <- app.Listener(listener) }()
	defer func() {
		if err := app.ShutdownWithTimeout(5 * time.Second); err != nil {
			t.Error(err)
		}
		select {
		case err := <-served:
			if err != nil {
				t.Error(err)
			}
		case <-time.After(5 * time.Second):
			t.Error("Fiber listener did not stop")
		}
	}()

	client := &http.Client{Timeout: 5 * time.Second}
	defer client.CloseIdleConnections()
	requests := []struct{ method, path string }{
		{http.MethodGet, "/sample_rate_route/1"},
		{http.MethodGet, "/returnheaders"},
		{http.MethodPut, "/"},
		{http.MethodPost, "/"},
		{http.MethodDelete, "/"},
		{http.MethodPatch, "/"},
		{http.MethodGet, "/"},
	}
	expectedMethods := make(map[string]string, len(requests))
	for _, request := range requests {
		requestID := request.method + " " + request.path
		expectedMethods[requestID] = request.method
		req, err := http.NewRequest(request.method, "http://"+listener.Addr().String()+request.path, nil)
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("User-Agent", requestID)
		res, err := client.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		_, readErr := io.Copy(io.Discard, res.Body)
		res.Body.Close()
		if readErr != nil || res.StatusCode != http.StatusOK {
			t.Fatalf("%s returned %d, read error: %v", requestID, res.StatusCode, readErr)
		}
	}
	servers := make(map[string]int)
	seenRequests := make(map[string]int)
	clients := 0
	for _, span := range mt.FinishedSpans() {
		component, _ := span.Tag("component").(string)
		if strings.Contains(component, "fasthttp") {
			t.Fatalf("duplicate fasthttp instrumentation: %v", span.Tags())
		}
		switch span.Tag("span.kind") {
		case "server":
			if component != "gofiber/fiber.v2" {
				t.Fatalf("unexpected server integration: %v", span.Tags())
			}
			route, _ := span.Tag("http.route").(string)
			servers[route]++
			path := route
			if route == "/sample_rate_route/:i" {
				path = "/sample_rate_route/1"
			}
			requestID, _ := span.Tag("system_tests.request.user_agent").(string)
			method, found := expectedMethods[requestID]
			if !found || requestID != method+" "+path {
				t.Fatalf("request buffer reuse changed the correlation tag: %v", span.Tags())
			}
			// Check only after every request, so reused method buffers have changed.
			if span.Tag("http.method") != method {
				t.Fatalf("request buffer reuse changed the method for %q: %v", requestID, span.Tags())
			}
			seenRequests[requestID]++
		case "client":
			if component == "net/http" {
				clients++
			}
		}
	}
	if len(servers) != 3 || servers["/sample_rate_route/:i"] != 1 || servers["/returnheaders"] != 1 || servers["/"] != 5 || clients != len(requests) {
		t.Fatalf("want one Fiber server and one HTTP client span per request, got servers=%v clients=%d", servers, clients)
	}
	for requestID := range expectedMethods {
		if seenRequests[requestID] != 1 {
			t.Fatalf("want one server span for %q, got %d", requestID, seenRequests[requestID])
		}
	}
}
