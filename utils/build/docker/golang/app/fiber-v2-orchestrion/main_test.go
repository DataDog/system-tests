package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"

	"github.com/gofiber/fiber/v2"
)

func request(t *testing.T, app *fiber.App, method, path, body, contentType string) (*http.Response, string) {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	res, err := app.Test(req, -1)
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	return res, string(data)
}

func TestRoutes(t *testing.T) {
	app := newApp()
	for _, tc := range []struct {
		method, path, body, contentType string
		status                          int
		want                            string
	}{
		{http.MethodGet, "/", "", "", 200, "Hello world!\n"},
		{http.MethodPost, "/", "", "", 200, "Hello world!\n"},
		{http.MethodGet, "/headers/", "", "", 200, "Hello, headers!\n"},
		{http.MethodGet, "/status", "", "", 200, "OK"},
		{http.MethodGet, "/status?code=503", "", "", 503, "OK"},
		{http.MethodGet, "/status?code=not-a-code", "", "", 400, "invalid status code"},
		{http.MethodGet, "/status?code=999", "", "", 400, "invalid status code"},
		{http.MethodGet, "/stats-unique?code=201", "", "", 201, "OK"},
		{http.MethodGet, "/params/value", "", "", 200, "OK"},
		{http.MethodGet, "/sample_rate_route/1", "", "", 200, "OK"},
		{http.MethodPost, "/waf/sub/path", `{"value":"test"}`, "application/json", 200, "Hello, WAF!\n"},
		{http.MethodOptions, "/waf", "", "", 200, "Hello, WAF!\n"},
		{http.MethodGet, "/tag_value/value/418", "", "", 418, "Value tagged"},
		{http.MethodGet, "/tag_value/value/bad", "", "", 400, "invalid status code"},
		{http.MethodPost, "/tag_value/payload_in_response_body/200", `{"value":"test"}`, "application/json", 200, `{"payload":{"value":"test"}}`},
		{http.MethodGet, "/session/user", "", "", 400, "missing session cookie"},
		{http.MethodGet, "/inferred-proxy/span-creation?status_code=404", "", "", 404, "ok"},
		{http.MethodGet, "/debugger/log", "", "", 200, "Log probe"},
		{http.MethodGet, "/debugger/budgets/2", "", "", 200, "Budgets"},
	} {
		t.Run(tc.method+" "+tc.path, func(t *testing.T) {
			res, body := request(t, app, tc.method, tc.path, tc.body, tc.contentType)
			if res.StatusCode != tc.status || body != tc.want {
				t.Fatalf("got (%d, %q), want (%d, %q)", res.StatusCode, body, tc.status, tc.want)
			}
		})
	}
	res, _ := request(t, app, http.MethodGet, "/not-found", "", "")
	if res.StatusCode != http.StatusNotFound {
		t.Fatalf("unknown route returned %d", res.StatusCode)
	}
}

func TestHealthcheck(t *testing.T) {
	t.Chdir(t.TempDir())
	app := newApp()
	res, _ := request(t, app, http.MethodGet, "/healthcheck", "", "")
	if res.StatusCode != http.StatusInternalServerError {
		t.Fatalf("missing version file returned %d", res.StatusCode)
	}
	if err := os.WriteFile("SYSTEM_TESTS_LIBRARY_VERSION", []byte("2.7.0"), 0600); err != nil {
		t.Fatal(err)
	}
	res, body := request(t, app, http.MethodGet, "/healthcheck", "", "")
	if res.StatusCode != 200 || res.Header.Get("Content-Type") != "application/json" {
		t.Fatalf("unexpected healthcheck response: %v", res)
	}
	if body != `{"status":"ok","library":{"name":"golang","version":"2.7.0"}}` {
		t.Fatalf("unexpected healthcheck body: %s", body)
	}
}

func TestResponseHeaders(t *testing.T) {
	app := newApp()
	res, _ := request(t, app, http.MethodGet, "/", "", "")
	if res.Header.Get("Content-Type") != "text/plain" || res.ContentLength != 13 {
		t.Fatalf("unexpected root headers: %v", res.Header)
	}
	res, _ = request(t, app, http.MethodGet, "/headers", "", "")
	if res.Header.Get("Content-Language") != "en-US" || res.ContentLength <= 0 {
		t.Fatalf("unexpected headers: %v", res.Header)
	}
	res, _ = request(t, app, http.MethodGet, "/tag_value/value/200?X-Test=first&X-Test=second", "", "")
	if res.Header.Get("X-Test") != "first, second" {
		t.Fatalf("query values were lost: %v", res.Header)
	}
	res, body := request(t, app, http.MethodGet, "/tag_value/value/200?%0d%0aX-Injected%3a%20v=1", "", "")
	if res.Header.Get("X-Injected") != "" || body != "Value tagged" {
		t.Fatalf("invalid header name changed the response: %v, %q", res.Header, body)
	}
	res, body = request(t, app, http.MethodGet, "/session/new", "", "")
	cookies := res.Cookies()
	if len(cookies) != 1 || cookies[0].Secure || !cookies[0].HttpOnly || cookies[0].Value != body {
		t.Fatalf("session cookie is not usable over HTTP: %v", cookies)
	}
}

func TestInvalidLoginBodies(t *testing.T) {
	app := newApp()
	for _, path := range []string{"/user_login_success_event_v2", "/user_login_failure_event_v2"} {
		res, _ := request(t, app, http.MethodPost, path, "{", "application/json")
		if res.StatusCode != http.StatusBadRequest {
			t.Fatalf("%s returned %d", path, res.StatusCode)
		}
	}
	res, _ := request(t, app, http.MethodPost, "/user_login_failure_event_v2", `{"exists":"invalid"}`, "application/json")
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("invalid exists returned %d", res.StatusCode)
	}
}

func TestHTTPHandlerPreservesContext(t *testing.T) {
	type key struct{}
	app := fiber.New()
	app.Use(func(c *fiber.Ctx) error {
		c.SetUserContext(context.WithValue(c.UserContext(), key{}, "fiber-context"))
		return c.Next()
	})
	app.Post("/shared", httpHandler(func(w http.ResponseWriter, r *http.Request) {
		if r.Context().Value(key{}) != "fiber-context" {
			t.Error("shared handler lost the Fiber context")
		}
		if r.Method != http.MethodPost || r.URL.Query().Get("q") != "value" || r.Header.Get("Content-Type") != "text/plain" {
			t.Errorf("shared handler received the wrong request: %v", r)
		}
		w.Header().Add("Set-Cookie", "first=1")
		w.Header().Add("Set-Cookie", "second=2")
		w.WriteHeader(http.StatusAccepted)
		io.Copy(w, r.Body)
	}))
	res, body := request(t, app, http.MethodPost, "/shared?q=value", "request body", "text/plain")
	if res.StatusCode != http.StatusAccepted || body != "request body" || len(res.Cookies()) != 2 {
		t.Fatalf("shared response was lost: %v, %q", res, body)
	}
}

func TestMakeDistantCall(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("downstream method = %s, want POST", r.Method)
		}
		w.Header().Set("X-Downstream", "present")
		w.WriteHeader(http.StatusCreated)
	}))
	defer server.Close()
	app := newApp()
	res, body := request(t, app, http.MethodGet, "/make_distant_call?method=POST&url="+url.QueryEscape(server.URL), "", "")
	var data struct {
		URL             string            `json:"url"`
		StatusCode      int               `json:"status_code"`
		ResponseHeaders map[string]string `json:"response_headers"`
	}
	if err := json.Unmarshal([]byte(body), &data); err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != 200 || data.URL != server.URL || data.StatusCode != 201 || data.ResponseHeaders["X-Downstream"] != "present" {
		t.Fatalf("unexpected downstream result: %s", body)
	}
	res, _ = request(t, app, http.MethodGet, "/make_distant_call?url=://invalid", "", "")
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("invalid URL returned %d", res.StatusCode)
	}
}
