package main

import (
	"context"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"
	"systemtests.weblog/_shared/dbm"
	"systemtests.weblog/_shared/grpc"
	"systemtests.weblog/_shared/rasp"

	"github.com/DataDog/dd-trace-go/v2/appsec"
	_ "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry/metric"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/adaptor"
	"github.com/sirupsen/logrus"
	"golang.org/x/net/http/httpguts"
)

func main() {
	logrus.SetFormatter(&logrus.JSONFormatter{})
	logrus.SetOutput(os.Stdout)
	logrus.SetLevel(logrus.DebugLevel)

	// Orchestrion starts the tracer and profiler and adds the tracing middleware.
	app := newApp()
	// Use automatic client instrumentation, as in net-http-orchestrion.
	rasp.HTTPClient = &http.Client{Transport: http.DefaultTransport}
	common.InitDatadog()
	go grpc.ListenAndServe()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGINT)
	defer signal.Stop(signals)
	go func() {
		if err := app.Listen(":7777"); err != nil {
			log.Fatal(err)
		}
	}()
	<-signals

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := app.ShutdownWithContext(ctx); err != nil {
		log.Printf("HTTP shutdown error: %v", err)
	}
}

func newApp() *fiber.App {
	app := fiber.New(fiber.Config{DisableStartupMessage: true})
	app.Use(func(c *fiber.Ctx) error {
		// Use a test-only tag for request correlation. Do not emulate HTTP tags
		// that the tracer does not capture. Clone values that outlive the request.
		if span, found := tracer.SpanFromContext(c.UserContext()); found {
			span.SetTag("system_tests.request.user_agent", strings.Clone(c.Get("User-Agent")))
		}
		return c.Next()
	})

	app.All("/", func(c *fiber.Ctx) error {
		c.Set("Content-Type", "text/plain")
		return c.SendString("Hello world!\n")
	})
	app.Get("/healthcheck", func(c *fiber.Ctx) error {
		health, err := common.GetHealtchCheck()
		if err != nil {
			return c.Status(http.StatusInternalServerError).SendString(err.Error())
		}
		return c.JSON(health)
	})
	app.All("/status", status)
	app.All("/stats-unique", status)
	app.All("/headers", func(c *fiber.Ctx) error {
		c.Set("Content-Type", "text/plain")
		c.Set("Content-Language", "en-US")
		return c.SendString("Hello, headers!\n")
	})
	app.All("/sample_rate_route/:i", ok)
	app.All("/params/:myParam", ok)
	app.All("/waf", waf)
	app.All("/waf/*", waf)
	app.All("/users", func(c *fiber.Ctx) error {
		if err := appsec.SetUser(c.UserContext(), strings.Clone(c.Query("user"))); err != nil {
			return nil
		}
		return c.SendString("Hello, " + c.Query("user"))
	})
	app.All("/tag_value/:tag_value/:status_code", tagValue)
	app.All("/identify", func(c *fiber.Ctx) error {
		if span, found := tracer.SpanFromContext(c.UserContext()); found {
			tracer.SetUser(span, "usr.id", tracer.WithUserEmail("usr.email"),
				tracer.WithUserName("usr.name"), tracer.WithUserSessionID("usr.session_id"),
				tracer.WithUserRole("usr.role"), tracer.WithUserScope("usr.scope"))
		}
		return c.SendString("Hello, identify!")
	})
	app.All("/identify-propagate", func(c *fiber.Ctx) error {
		if span, found := tracer.SpanFromContext(c.UserContext()); found {
			tracer.SetUser(span, "usr.id", tracer.WithPropagation())
		}
		return c.SendString("Hello, identify-propagate!")
	})
	app.All("/make_distant_call", makeDistantCall)
	app.All("/trace/manual_keep_drop", httpHandler(common.ManualKeepDrop))
	app.All("/security/thread_context_sharing", httpHandler(common.ThreadContextSharing))

	app.Get("/user_login_success_event", func(c *fiber.Ctx) error {
		appsec.TrackUserLoginSuccessEvent(c.UserContext(), strings.Clone(c.Query("event_user_id", "system_tests_user")), eventMetadata())
		return nil
	})
	app.Get("/user_login_failure_event", func(c *fiber.Ctx) error {
		exists, err := strconv.ParseBool(c.Query("event_user_exists", "true"))
		if err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		appsec.TrackUserLoginFailureEvent(c.UserContext(), strings.Clone(c.Query("event_user_id", "system_tests_user")), exists, eventMetadata())
		return nil
	})
	app.Post("/user_login_success_event_v2", func(c *fiber.Ctx) error {
		var data struct {
			Login    string            `json:"login"`
			UserID   string            `json:"user_id"`
			Metadata map[string]string `json:"metadata"`
		}
		if err := c.BodyParser(&data); err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		appsec.TrackUserLoginSuccess(c.UserContext(), strings.Clone(data.Login), strings.Clone(data.UserID), cloneMetadata(data.Metadata))
		return nil
	})
	app.Post("/user_login_failure_event_v2", func(c *fiber.Ctx) error {
		var data struct {
			Login    string            `json:"login"`
			Exists   string            `json:"exists"`
			Metadata map[string]string `json:"metadata"`
		}
		if err := c.BodyParser(&data); err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		exists, err := strconv.ParseBool(data.Exists)
		if err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		appsec.TrackUserLoginFailure(c.UserContext(), strings.Clone(data.Login), exists, cloneMetadata(data.Metadata))
		return nil
	})
	app.Get("/custom_event", func(c *fiber.Ctx) error {
		appsec.TrackCustomEvent(c.UserContext(), strings.Clone(c.Query("event_name", "system_tests_event")), eventMetadata())
		return nil
	})
	app.Get("/read_file", func(c *fiber.Ctx) error {
		data, err := os.ReadFile(c.Query("file"))
		if err != nil {
			return c.Status(http.StatusInternalServerError).SendString(err.Error())
		}
		return c.Send(data)
	})
	app.Get("/session/new", func(c *fiber.Ctx) error {
		id := strconv.Itoa(rand.Int())
		c.Cookie(&fiber.Cookie{Name: "session", Value: id, Path: "/", MaxAge: 3600, HTTPOnly: true})
		return c.SendString(id)
	})
	app.Get("/session/user", func(c *fiber.Ctx) error {
		id := strings.Clone(c.Cookies("session"))
		if id == "" {
			return c.Status(http.StatusBadRequest).SendString("missing session cookie")
		}
		appsec.TrackUserLoginSuccessEvent(c.UserContext(), strings.Clone(c.Query("sdk_user")), map[string]string{}, tracer.WithUserSessionID(id))
		return nil
	})
	app.Get("/inferred-proxy/span-creation", func(c *fiber.Ctx) error {
		code, err := parseStatus(c.Query("status_code", "200"))
		if err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		return c.Status(code).SendString("ok")
	})
	app.Get("/log/library", func(c *fiber.Ctx) error {
		entry := logrus.WithContext(c.UserContext())
		message := c.Query("msg", "msg")
		switch c.Query("level") {
		case "warn":
			entry.Warn(message)
		case "error":
			entry.Error(message)
		case "debug":
			entry.Debug(message)
		default:
			entry.Info(message)
		}
		return c.SendString("OK")
	})

	app.All("/rasp/lfi", httpHandler(rasp.LFI))
	app.All("/rasp/multiple", httpHandler(rasp.LFIMultiple))
	app.All("/rasp/ssrf", httpHandler(rasp.SSRF))
	app.All("/rasp/sqli", httpHandler(rasp.SQLi))
	app.All("/rasp/cmdi", httpHandler(rasp.CMDI))
	app.All("/external_request", httpHandler(rasp.ExternalRequest))
	app.Get("/external_request/redirect", httpHandler(rasp.ExternalRedirectRequest))
	app.All("/stub_dbm", httpHandler(dbm.StubDbmHandler))
	app.All("/requestdownstream", httpHandler(common.Requestdownstream))
	app.All("/returnheaders", httpHandler(common.Returnheaders))
	app.All("/ffe", httpHandler(common.FFeEval()))

	var debugger DebuggerController
	app.All("/debugger/log", httpHandler(debugger.logProbe))
	app.All("/debugger/mix", httpHandler(debugger.mixProbe))
	app.All("/debugger/expression", httpHandler(debugger.expression))
	app.All("/debugger/budgets/:count", func(c *fiber.Ctx) error {
		loops, _ := strconv.Atoi(c.Params("count"))
		return httpHandler(func(w http.ResponseWriter, r *http.Request) {
			debugger.budgets(w, r, loops)
		})(c)
	})
	return app
}

func ok(c *fiber.Ctx) error {
	return c.SendString("OK")
}

func parseStatus(value string) (int, error) {
	code, err := strconv.Atoi(value)
	if err != nil || code < 200 || code > 599 {
		return 0, fiber.NewError(http.StatusBadRequest, "invalid status code")
	}
	return code, nil
}

func status(c *fiber.Ctx) error {
	code, err := parseStatus(c.Query("code", "200"))
	if err != nil {
		return c.Status(http.StatusBadRequest).SendString(err.Error())
	}
	return c.Status(code).SendString("OK")
}

func waf(c *fiber.Ctx) error {
	req, err := adaptor.ConvertRequest(c, true)
	if err != nil {
		return c.Status(http.StatusBadRequest).SendString(err.Error())
	}
	if body, err := common.ParseBody(req); err == nil {
		if err := appsec.MonitorParsedHTTPBody(c.UserContext(), body); err != nil {
			return nil
		}
	}
	return c.SendString("Hello, WAF!\n")
}

func tagValue(c *fiber.Ctx) error {
	tag := strings.Clone(c.Params("tag_value"))
	code, err := parseStatus(c.Params("status_code"))
	if err != nil {
		return c.Status(http.StatusBadRequest).SendString(err.Error())
	}
	if span, found := tracer.SpanFromContext(c.UserContext()); found {
		span.SetTag("appsec.events.system_tests_appsec_event.value", tag)
	}
	c.Request().URI().QueryArgs().VisitAll(func(key, value []byte) {
		if httpguts.ValidHeaderFieldName(string(key)) {
			c.Append(string(key), string(value))
		}
	})
	var body any
	if len(c.Body()) > 0 {
		req, err := adaptor.ConvertRequest(c, true)
		if err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		body, err = common.ParseBody(req)
		if err != nil {
			return c.Status(http.StatusBadRequest).SendString(err.Error())
		}
		if err := appsec.MonitorParsedHTTPBody(c.UserContext(), body); err != nil {
			return nil
		}
	}
	if c.Method() == http.MethodPost && strings.HasPrefix(tag, "payload_in_response_body") {
		return c.Status(code).JSON(map[string]any{"payload": body})
	}
	return c.Status(code).SendString("Value tagged")
}

func eventMetadata() map[string]string {
	return map[string]string{"metadata0": "value0", "metadata1": "value1"}
}

// BodyParser can return form values backed by Fiber's request buffer.
func cloneMetadata(metadata map[string]string) map[string]string {
	if metadata == nil {
		return nil
	}
	copy := make(map[string]string, len(metadata))
	for key, value := range metadata {
		copy[strings.Clone(key)] = strings.Clone(value)
	}
	return copy
}

func makeDistantCall(c *fiber.Ctx) error {
	url := strings.Clone(c.Query("url"))
	if url == "" {
		return c.SendString("OK")
	}
	req, err := http.NewRequestWithContext(c.UserContext(), strings.Clone(c.Query("method", http.MethodGet)), url, nil)
	if err != nil {
		return c.Status(http.StatusBadRequest).SendString(err.Error())
	}
	// The instrumented client injects into a copy. Keep headers visible to tests.
	if span, found := tracer.SpanFromContext(c.UserContext()); found {
		if err := tracer.Inject(span.Context(), tracer.HTTPHeadersCarrier(req.Header)); err != nil {
			return c.Status(http.StatusInternalServerError).SendString(err.Error())
		}
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		return c.Status(http.StatusBadGateway).SendString(err.Error())
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
	return c.JSON(struct {
		URL             string            `json:"url"`
		StatusCode      int               `json:"status_code"`
		RequestHeaders  map[string]string `json:"request_headers"`
		ResponseHeaders map[string]string `json:"response_headers"`
	}{url, res.StatusCode, requestHeaders, responseHeaders})
}

// httpHandler preserves the Fiber span when calling a shared net/http handler.
// The adapter does not start an http.Server, so Fiber owns the only server span.
func httpHandler(handler http.HandlerFunc) fiber.Handler {
	return func(c *fiber.Ctx) error {
		return adaptor.HTTPHandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			handler(w, r.WithContext(c.UserContext()))
		})(c)
	}
}
