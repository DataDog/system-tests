package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"
	"systemtests.weblog/_shared/grpc"
	"systemtests.weblog/_shared/rasp"

	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	echotrace "github.com/DataDog/dd-trace-go/contrib/labstack/echo.v4/v2"
	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	dd_logrus "github.com/DataDog/dd-trace-go/contrib/sirupsen/logrus/v2"
	"github.com/DataDog/dd-trace-go/v2/appsec"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/DataDog/dd-trace-go/v2/profiler"
)

func main() {
	logrus.SetFormatter(&logrus.JSONFormatter{})
	logrus.SetOutput(os.Stdout)
	logrus.SetLevel(logrus.DebugLevel)

	// Add Datadog context log hook
	logrus.AddHook(&dd_logrus.DDContextLogHook{})

	tracer.Start()
	defer tracer.Stop()

	err := profiler.Start(
		profiler.WithService("weblog"),
		profiler.WithEnv("system-tests"),
		profiler.WithVersion("1.0"),
		profiler.WithTags(),
		profiler.WithProfileTypes(profiler.CPUProfile, profiler.HeapProfile),
	)

	if err != nil {
		logrus.Fatal(err)
	}
	defer profiler.Stop()

	r := echo.New()

	r.Use(echotrace.Middleware())

	r.Any("/", func(c echo.Context) error {
		return c.NoContent(http.StatusOK)
	})

	r.GET("/healthcheck", func(c echo.Context) error {
		healthCheck, err := common.GetHealtchCheck()

		if err != nil {
			return c.JSON(http.StatusInternalServerError, err)
		}

		return c.JSON(http.StatusOK, healthCheck)
	})

	r.Any("/*", func(c echo.Context) error {
		return c.NoContent(http.StatusNotFound)
	})

	r.Any("/status", func(c echo.Context) error {
		rCode := 200
		if codeStr := c.Request().URL.Query().Get("code"); codeStr != "" {
			if code, err := strconv.Atoi(codeStr); err == nil {
				rCode = code
			}
		}
		return c.NoContent(rCode)
	})

	r.Any("/stats-unique", func(c echo.Context) error {
		rCode := 200
		if codeStr := c.Request().URL.Query().Get("code"); codeStr != "" {
			if code, err := strconv.Atoi(codeStr); err == nil {
				rCode = code
			}
		}
		return c.NoContent(rCode)
	})

	r.Any("/waf", waf)
	r.Any("/waf/*", waf)

	r.Any("/users", func(c echo.Context) error {
		userID := c.QueryParam("user")
		if err := appsec.SetUser(c.Request().Context(), userID); err != nil {
			return err
		}

		return c.String(http.StatusOK, "Hello, "+userID)
	})

	r.Any("/sample_rate_route/:i", func(c echo.Context) error {
		return c.String(http.StatusOK, "OK")
	})

	r.Any("/params/:i", func(c echo.Context) error {
		return c.String(http.StatusOK, "OK")
	})

	r.Any("/tag_value/:tag_value/:status_code", func(c echo.Context) error {
		tag := c.Param("tag_value")
		status, _ := strconv.Atoi(c.Param("status_code"))
		span, _ := tracer.SpanFromContext(c.Request().Context())
		span.SetTag("appsec.events.system_tests_appsec_event.value", tag)
		for key, values := range c.QueryParams() {
			for _, value := range values {
				c.Response().Header().Add(key, value)
			}
		}

		var bodyMap map[string]any
		switch {
		case c.Request().Header.Get("Content-Type") == "application/json":
			dec := json.NewDecoder(c.Request().Body)
			dec.UseNumber()
			if err := dec.Decode(&bodyMap); err != nil {
				return err
			}
			appsec.MonitorParsedHTTPBody(c.Request().Context(), bodyMap)
		case c.Request().ParseForm() == nil:
			bodyMap = make(map[string]any) // Bind assumes this is non-nil...
			if err := c.Bind(&bodyMap); err != nil {
				return err
			}
			appsec.MonitorParsedHTTPBody(c.Request().Context(), c.Request().PostForm)
		default:
			logrus.Warnf("Unsupported request content-type: %q", c.Request().Header.Get("Content-Type"))
		}

		if c.Request().Method == http.MethodPost && strings.HasPrefix(tag, "payload_in_response_body") {
			return c.JSON(status, map[string]any{"payload": bodyMap})
		}

		return c.String(status, "Value tagged")
	})

	r.Any("/status", func(c echo.Context) error {
		rCode := 200
		if codeStr := c.Request().URL.Query().Get("code"); codeStr != "" {
			if code, err := strconv.Atoi(codeStr); err == nil {
				rCode = code
			}
		}
		return c.String(rCode, "OK")
	})

	r.Any("/make_distant_call", func(c echo.Context) error {
		url := c.Request().URL.Query().Get("url")
		if url == "" {
			return c.String(200, "OK")
		}

		client := httptrace.WrapClient(http.DefaultClient)
		req, _ := http.NewRequestWithContext(c.Request().Context(), http.MethodGet, url, nil)
		res, err := client.Do(req)
		if err != nil {
			logrus.Fatalln(err)
		}

		defer res.Body.Close()

		requestHeaders := make(map[string]string, len(req.Header))
		for key, values := range req.Header {
			requestHeaders[key] = strings.Join(values, ",")
		}

		responseHeaders := make(map[string]string, len(res.Header))
		for key, values := range res.Header {
			responseHeaders[key] = strings.Join(values, ",")
		}

		return c.JSON(200, struct {
			URL             string            `json:"url"`
			StatusCode      int               `json:"status_code"`
			RequestHeaders  map[string]string `json:"request_headers"`
			ResponseHeaders map[string]string `json:"response_headers"`
		}{URL: url, StatusCode: res.StatusCode, RequestHeaders: requestHeaders, ResponseHeaders: responseHeaders})
	})

	r.Any("/headers/", headers)
	r.Any("/headers", headers)

	identify := func(c echo.Context) error {
		if span, ok := tracer.SpanFromContext(c.Request().Context()); ok {
			tracer.SetUser(
				span, "usr.id", tracer.WithUserEmail("usr.email"),
				tracer.WithUserName("usr.name"), tracer.WithUserSessionID("usr.session_id"),
				tracer.WithUserRole("usr.role"), tracer.WithUserScope("usr.scope"),
			)
		}
		return c.String(http.StatusOK, "Hello, identify!")
	}
	r.Any("/identify/", identify)
	r.Any("/identify", identify)
	r.Any("/identify-propagate", func(c echo.Context) error {
		if span, ok := tracer.SpanFromContext(c.Request().Context()); ok {
			tracer.SetUser(span, "usr.id", tracer.WithPropagation())
		}
		return c.String(http.StatusOK, "Hello, identify-propagate!")
	})

	r.GET("/user_login_success_event", func(ctx echo.Context) error {
		uid := "system_tests_user"
		if q := ctx.QueryParam("event_user_id"); q != "" {
			uid = q
		}
		appsec.TrackUserLoginSuccessEvent(ctx.Request().Context(), uid, map[string]string{"metadata0": "value0", "metadata1": "value1"})
		return nil
	})

	r.POST("/user_login_success_event_v2", func(ctx echo.Context) error {
		var data struct {
			Login    string            `json:"login"`
			UserID   string            `json:"user_id"`
			Metadata map[string]string `json:"metadata"`
		}
		if err := ctx.Bind(&data); err != nil {
			logrus.Println("error decoding request body for", ctx.Request().URL, ":", err)
			return err
		}

		appsec.TrackUserLoginSuccess(ctx.Request().Context(), data.Login, data.UserID, data.Metadata)
		return nil
	})

	r.GET("/user_login_failure_event", func(ctx echo.Context) error {
		uid := "system_tests_user"
		if q := ctx.QueryParam("event_user_id"); q != "" {
			uid = q
		}
		exists := true
		if q := ctx.QueryParam("event_user_exists"); q != "" {
			parsed, err := strconv.ParseBool(q)
			if err != nil {
				exists = parsed
			}
		}
		appsec.TrackUserLoginFailureEvent(ctx.Request().Context(), uid, exists, map[string]string{"metadata0": "value0", "metadata1": "value1"})
		return nil
	})

	r.POST("/user_login_failure_event_v2", func(ctx echo.Context) error {
		var data struct {
			Login    string            `json:"login"`
			Exists   string            `json:"exists"`
			Metadata map[string]string `json:"metadata"`
		}
		if err := ctx.Bind(&data); err != nil {
			logrus.Println("error decoding request body for ", ctx.Request().URL, ":", err)
			return err
		}

		exists, err := strconv.ParseBool(data.Exists)
		if err != nil {
			logrus.Printf("error parsing exists value %q: %v\n", data.Exists, err)
			return err
		}

		appsec.TrackUserLoginFailure(ctx.Request().Context(), data.Login, exists, data.Metadata)
		return nil
	})

	r.GET("/custom_event", func(ctx echo.Context) error {
		name := "system_tests_event"
		if q := ctx.QueryParam("event_name"); q != "" {
			name = q
		}
		appsec.TrackCustomEvent(ctx.Request().Context(), name, map[string]string{"metadata0": "value0", "metadata1": "value1"})
		return nil
	})

	r.GET("/read_file", func(ctx echo.Context) error {
		path := ctx.QueryParam("file")
		content, err := os.ReadFile(path)

		if err != nil {
			logrus.Fatalln(err)
			return ctx.String(500, "KO")
		}

		return ctx.String(http.StatusOK, string(content))
	})

	r.GET("/session/new", func(ctx echo.Context) error {
		sessionID := strconv.Itoa(rand.Int())
		ctx.SetCookie(&http.Cookie{
			Name:     "session",
			Value:    sessionID,
			MaxAge:   3600,
			Secure:   true,
			HttpOnly: true,
		})
		return ctx.NoContent(200)
	})

	r.GET("/session/user", func(ctx echo.Context) error {
		user := ctx.Request().URL.Query().Get("sdk_user")
		cookie, err := ctx.Request().Cookie("session")
		if err != nil {
			return ctx.String(500, "no session cookie")
		}
		appsec.TrackUserLoginSuccessEvent(ctx.Request().Context(), user, map[string]string{}, tracer.WithUserSessionID(cookie.Value))
		return ctx.NoContent(200)
	})

	r.GET("/inferred-proxy/span-creation", func(ctx echo.Context) error {
		statusCodeStr := ctx.Request().URL.Query().Get("status_code")
		statusCode := 200
		if statusCodeStr != "" {
			var err error
			statusCode, err = strconv.Atoi(statusCodeStr)
			if err != nil {
				statusCode = 400
				return ctx.String(statusCode, "no inferred span")
			}
		}

		// Log the request headers
		fmt.Println("Received an API Gateway request")
		for key, values := range ctx.Request().Header {
			for _, value := range values {
				fmt.Printf("%s: %s\n", key, value)
			}
		}

		return ctx.String(statusCode, "ok")
	})

	r.GET("/log/library", func(ctx echo.Context) error {
		reqCtx := ctx.Request()
		msg := reqCtx.URL.Query().Get("msg")
		if msg == "" {
			msg = "msg"
		}
		switch reqCtx.URL.Query().Get("level") {
		case "warn":
			logrus.WithContext(reqCtx.Context()).Warn(msg)
		case "error":
			logrus.WithContext(reqCtx.Context()).Error(msg)
		case "debug":
			logrus.WithContext(reqCtx.Context()).Debug(msg)
		default:
			logrus.WithContext(reqCtx.Context()).Info(msg)
		}
		return ctx.NoContent(200)
	})

	r.Any("/rasp/lfi", echoHandleFunc(rasp.LFI))
	r.Any("/rasp/ssrf", echoHandleFunc(rasp.SSRF))
	r.Any("/rasp/sqli", echoHandleFunc(rasp.SQLi))

	r.Any("/requestdownstream", echoHandleFunc(common.Requestdownstream))
	r.Any("/returnheaders", echoHandleFunc(common.Returnheaders))

	common.InitDatadog()
	go grpc.ListenAndServe()
	go func() {
		if err := r.Start(":7777"); !errors.Is(err, http.ErrServerClosed) {
			logrus.Fatal(err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, syscall.SIGTERM)
	<-c

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := r.Shutdown(ctx); err != nil {
		logrus.Fatalf("HTTP shutdown error: %v", err)
	}

}

func echoHandleFunc(handlerFunc http.HandlerFunc) echo.HandlerFunc {
	return func(c echo.Context) error {
		handlerFunc(c.Response().Writer, c.Request())
		return nil
	}
}

func headers(c echo.Context) error {
	//Data used for header content is irrelevant here, only header presence is checked
	c.Response().Writer.Header().Set("content-type", "text/plain")
	c.Response().Writer.Header().Set("content-length", "42")
	c.Response().Writer.Header().Set("content-language", "en-US")

	return c.String(http.StatusOK, "Hello, headers!")
}

func waf(c echo.Context) error {
	req := c.Request()
	body, err := common.ParseBody(req)
	if err == nil {
		appsec.MonitorParsedHTTPBody(req.Context(), body)
	}
	return c.String(http.StatusOK, "Hello, WAF!\n")
}
