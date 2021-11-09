package main

import (
	"net/http"

	"github.com/labstack/echo/v4"

	echotrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/labstack/echo.v4"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start(tracer.WithServiceName("weblog"))
	defer tracer.Stop()

	r := echo.New()

	r.Use(echotrace.Middleware())

	r.Any("/", func(c echo.Context) error {
		return c.NoContent(http.StatusOK)
	})

	r.Any("/waf/", func(c echo.Context) error {
		span, _ := tracer.SpanFromContext(c.Request().Context())
		span.SetTag("http.request.headers.user-agent", c.Request().UserAgent())
		return c.String(http.StatusOK, "Hello, WAF!\n")
	})

	r.Any("/sample_rate_route/:i", func(c echo.Context) error {
		return c.String(http.StatusOK, "OK")
	})

	initDatadog()
	r.Start(":7777")
}

func initDatadog() {
	span := tracer.StartSpan("init.service")
	defer span.Finish()
	span.SetTag("whip", "done")
}
