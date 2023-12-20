package main

import (
	"log"
	"net/http"
	"os"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/DataDog/dd-trace-go/v2/appsec"
	gintrace "github.com/DataDog/dd-trace-go/v2/contrib/gin-gonic/gin"
	httptrace "github.com/DataDog/dd-trace-go/v2/contrib/net/http"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	r := gin.New()
	r.Use(gintrace.Middleware("weblog"))

	r.Any("/", func(ctx *gin.Context) {
		ctx.Writer.WriteHeader(http.StatusOK)
	})
	r.Any("/waf", func(ctx *gin.Context) {
		body, err := parseBody(ctx.Request)
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
		ctx.Writer.WriteHeader(status)
		ctx.Writer.Write([]byte("Value tagged"))
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
		if url := ctx.Request.URL.Query().Get("url"); url != "" {

			client := httptrace.WrapClient(http.DefaultClient)
			req, _ := http.NewRequestWithContext(ctx.Request.Context(), http.MethodGet, url, nil)
			_, err := client.Do(req)

			if err != nil {
				log.Fatalln(err)
				ctx.Writer.WriteHeader(500)
			}
		}
		ctx.Writer.Write([]byte("OK"))
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
		appsec.TrackUserLoginSuccessEvent(ctx.Request.Context(), uid, map[string]string{"metadata0": "value0", "metadata1": "value1"})
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
		appsec.TrackUserLoginFailureEvent(ctx.Request.Context(), uid, exists, map[string]string{"metadata0": "value0", "metadata1": "value1"})
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

	initDatadog()
	go listenAndServeGRPC()
	http.ListenAndServe(":7777", r)
}

func headers(ctx *gin.Context) {
	//Data used for header content is irrelevant here, only header presence is checked
	ctx.Writer.Header().Set("content-type", "text/plain")
	ctx.Writer.Header().Set("content-length", "42")
	ctx.Writer.Header().Set("content-language", "en-US")
	ctx.Writer.Write([]byte("Hello, headers!"))
}
