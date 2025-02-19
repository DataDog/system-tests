package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"weblog/internal/common"
	"weblog/internal/grpc"
	"weblog/internal/rasp"

	"github.com/gin-gonic/gin"

	gintrace "github.com/DataDog/dd-trace-go/contrib/gin-gonic/gin/v2"
	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	"github.com/DataDog/dd-trace-go/v2/appsec"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/DataDog/dd-trace-go/v2/profiler"
)

func main() {
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
		log.Fatal(err)
	}
	defer profiler.Stop()

	r := gin.New()
	r.Use(gintrace.Middleware("weblog"))

	r.Any("/", func(ctx *gin.Context) {
		ctx.Writer.WriteHeader(http.StatusOK)
	})
	r.Any("/stats-unique", func(ctx *gin.Context) {
		if c := ctx.Request.URL.Query().Get("code"); c != "" {
			if code, err := strconv.Atoi(c); err == nil {
				ctx.Writer.WriteHeader(code)
				return
			}
		}
		ctx.Writer.WriteHeader(http.StatusOK)
	})

	r.GET("/healthcheck", func(ctx *gin.Context) {
		healthCheck, err := common.GetHealtchCheck()

		if err != nil {
			ctx.JSON(http.StatusInternalServerError, err)
		}

		ctx.JSON(http.StatusOK, healthCheck)
	})

	r.Any("/waf", func(ctx *gin.Context) {
		body, err := common.ParseBody(ctx.Request)
		if err == nil {
			appsec.MonitorParsedHTTPBody(ctx.Request.Context(), body)
		}
		ctx.Writer.Write([]byte("Hello, WAF!\n"))
	})
	r.Any("/users", func(ctx *gin.Context) {
		userId := ctx.Query("user")
		if appsec.SetUser(ctx.Request.Context(), ctx.Query("user")) != nil {
			return
		}
		ctx.Writer.Write([]byte("Hello, " + userId))
	})
	r.Any("/waf/*allpaths", func(ctx *gin.Context) {
		ctx.Writer.Write([]byte("Hello, WAF!\n"))
	})
	r.Any("/sample_rate_route/:i", func(ctx *gin.Context) {
		ctx.Writer.Write([]byte("OK"))
	})
	r.Any("/params/:myParam", func(ctx *gin.Context) {
		ctx.Writer.Write([]byte("OK"))
	})

	r.Any("/tag_value/:tag_value/:status_code", func(ctx *gin.Context) {
		tag := ctx.Param("tag_value")
		status, _ := strconv.Atoi(ctx.Param("status_code"))
		span, _ := tracer.SpanFromContext(ctx.Request.Context())
		span.SetTag("appsec.events.system_tests_appsec_event.value", tag)
		for key, values := range ctx.Request.URL.Query() {
			for _, value := range values {
				ctx.Writer.Header().Add(key, value)
			}
		}
		ctx.Writer.WriteHeader(status)
		ctx.Writer.Write([]byte("Value tagged"))
		switch {
		case ctx.Request.Header.Get("Content-Type") == "application/json":
			body, _ := io.ReadAll(ctx.Request.Body)
			var bodyMap map[string]any
			if err := json.Unmarshal(body, &bodyMap); err == nil {
				appsec.MonitorParsedHTTPBody(ctx.Request.Context(), bodyMap)
			}
		case ctx.Request.ParseForm() == nil:
			appsec.MonitorParsedHTTPBody(ctx.Request.Context(), ctx.Request.PostForm)
		}
	})

	r.Any("/status", func(ctx *gin.Context) {
		if c := ctx.Request.URL.Query().Get("code"); c != "" {
			if code, err := strconv.Atoi(c); err == nil {
				ctx.Writer.WriteHeader(code)
			}
		}
		ctx.Writer.Write([]byte("OK"))
	})

	r.Any("/make_distant_call", func(ctx *gin.Context) {
		url := ctx.Request.URL.Query().Get("url")
		if url == "" {
			ctx.Writer.Write([]byte("OK"))
			return
		}

		client := httptrace.WrapClient(http.DefaultClient)
		req, _ := http.NewRequestWithContext(ctx.Request.Context(), http.MethodGet, url, nil)
		res, err := client.Do(req)
		if err != nil {
			log.Fatalln(err)
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

		ctx.JSON(200, struct {
			URL             string            `json:"url"`
			StatusCode      int               `json:"status_code"`
			RequestHeaders  map[string]string `json:"request_headers"`
			ResponseHeaders map[string]string `json:"response_headers"`
		}{URL: url, StatusCode: res.StatusCode, RequestHeaders: requestHeaders, ResponseHeaders: responseHeaders})
	})

	r.Any("/headers/", headers)
	r.Any("/headers", headers)

	identify := func(ctx *gin.Context) {
		if span, ok := tracer.SpanFromContext(ctx.Request.Context()); ok {
			tracer.SetUser(
				span, "usr.id", tracer.WithUserEmail("usr.email"),
				tracer.WithUserName("usr.name"), tracer.WithUserSessionID("usr.session_id"),
				tracer.WithUserRole("usr.role"), tracer.WithUserScope("usr.scope"),
			)
		}
		ctx.Writer.Write([]byte("Hello, identify!"))
	}
	r.Any("/identify/", identify)
	r.Any("/identify", identify)
	r.Any("/identify-propagate", func(ctx *gin.Context) {
		if span, ok := tracer.SpanFromContext(ctx.Request.Context()); ok {
			tracer.SetUser(span, "usr.id", tracer.WithPropagation())
		}
		ctx.Writer.Write([]byte("Hello, identify-propagate!"))
	})

	r.GET("/user_login_success_event", func(ctx *gin.Context) {
		uid := "system_tests_user"
		if q := ctx.Query("event_user_id"); q != "" {
			uid = q
		}
		appsec.TrackUserLoginSuccess(ctx.Request.Context(), uid, uid, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	r.GET("/user_login_failure_event", func(ctx *gin.Context) {
		uid := "system_tests_user"
		if q := ctx.Query("event_user_id"); q != "" {
			uid = q
		}
		exists := true
		if q := ctx.Query("event_user_exists"); q != "" {
			parsed, err := strconv.ParseBool(q)
			if err != nil {
				exists = parsed
			}
		}
		appsec.TrackUserLoginFailure(ctx.Request.Context(), uid, exists, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	r.GET("/custom_event", func(ctx *gin.Context) {
		name := "system_tests_event"
		if q := ctx.Query("event_name"); q != "" {
			name = q
		}
		appsec.TrackCustomEvent(ctx.Request.Context(), name, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	r.GET("/read_file", func(ctx *gin.Context) {
		path := ctx.Query("file")
		content, err := os.ReadFile(path)

		if err != nil {
			log.Fatalln(err)
			ctx.Writer.WriteHeader(500)
		}
		ctx.Writer.Write(content)
	})

	r.GET("/session/new", func(ctx *gin.Context) {
		sessionID := strconv.Itoa(rand.Int())
		ctx.SetCookie("session", sessionID, 3600, "/", "", false, true)
	})

	r.GET("/session/user", func(ctx *gin.Context) {
		user := ctx.Query("sdk_user")
		cookie, err := ctx.Request.Cookie("session")
		if err != nil {
			ctx.Writer.WriteHeader(500)
		}
		appsec.TrackUserLoginSuccess(ctx.Request.Context(), user, map[string]string{}, tracer.WithUserSessionID(cookie.Value))
	})

	r.GET("/inferred-proxy/span-creation", func(ctx *gin.Context) {
		statusCodeStr := ctx.Query("status_code")
		statusCode := 200
		if statusCodeStr != "" {
			var err error
			statusCode, err = strconv.Atoi(statusCodeStr)
			if err != nil {
				statusCode = 400
			}
		}

		// Log the request headers
		fmt.Println("Received an API Gateway request")
		for key, values := range ctx.Request.Header {
			for _, value := range values {
				fmt.Printf("%s: %s\n", key, value)
			}
		}

		// Send the response
		ctx.Writer.WriteHeader(statusCode)
		ctx.Writer.Write([]byte("ok"))
	})

	r.Any("/rasp/lfi", ginHandleFunc(rasp.LFI))
	r.Any("/rasp/ssrf", ginHandleFunc(rasp.SSRF))
	r.Any("/rasp/sqli", ginHandleFunc(rasp.SQLi))

	r.Any("/requestdownstream", ginHandleFunc(common.Requestdownstream))
	r.Any("/returnheaders", ginHandleFunc(common.Returnheaders))

	srv := &http.Server{
		Addr:    ":7777",
		Handler: r,
	}

	common.InitDatadog()
	go grpc.ListenAndServe()
	go func() {
		if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, syscall.SIGTERM)
	<-c

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("HTTP shutdown error: %v", err)
	}
}

func ginHandleFunc(handlerFunc http.HandlerFunc) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		handlerFunc(ctx.Writer, ctx.Request)
	}
}

func headers(ctx *gin.Context) {
	//Data used for header content is irrelevant here, only header presence is checked
	ctx.Writer.Header().Set("content-type", "text/plain")
	ctx.Writer.Header().Set("content-length", "42")
	ctx.Writer.Header().Set("content-language", "en-US")
	ctx.Writer.Write([]byte("Hello, headers!"))
}
