package main

import (
	"encoding/json"
	"io"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strconv"

	"weblog/internal/common"
	"weblog/internal/grpc"
	"weblog/internal/rasp"

	"github.com/labstack/echo/v4"

	"gopkg.in/DataDog/dd-trace-go.v1/appsec"
	echotrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/labstack/echo.v4"
	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

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

		switch {
		case c.Request().Header.Get("Content-Type") == "application/json":
			body, _ := io.ReadAll(c.Request().Body)
			var bodyMap map[string]any
			if err := json.Unmarshal(body, &bodyMap); err == nil {
				appsec.MonitorParsedHTTPBody(c.Request().Context(), bodyMap)
			}
		case c.Request().ParseForm() == nil:
			appsec.MonitorParsedHTTPBody(c.Request().Context(), c.Request().PostForm)
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
		if url := c.Request().URL.Query().Get("url"); url != "" {

			client := httptrace.WrapClient(http.DefaultClient)
			req, _ := http.NewRequestWithContext(c.Request().Context(), http.MethodGet, url, nil)
			_, err := client.Do(req)

			if err != nil {
				log.Fatalln(err)
				return c.String(500, "KO")
			}
		}
		return c.String(200, "OK")
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
			log.Fatalln(err)
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

	r.Any("/rasp/lfi", echoHandleFunc(rasp.LFI))
	r.Any("/rasp/ssrf", echoHandleFunc(rasp.SSRF))
	r.Any("/rasp/sqli", echoHandleFunc(rasp.SQLi))

	common.InitDatadog()
	go grpc.ListenAndServe()
	r.Start(":7777")
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
