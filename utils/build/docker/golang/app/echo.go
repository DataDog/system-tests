package main

import (
	"net/http"

	"github.com/labstack/echo/v4"

	echotrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/labstack/echo.v4"
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

	r.Any("/*", func(c echo.Context) error {
		return c.NoContent(http.StatusNotFound)
	})

	r.Any("/waf/", func(c echo.Context) error {
		return c.String(http.StatusOK, "Hello, WAF!\n")
	})

	r.Any("/sample_rate_route/:i", func(c echo.Context) error {
		return c.String(http.StatusOK, "OK")
	})

	r.Any("/params/:i", func(c echo.Context) error {
		return c.String(http.StatusOK, "OK")
	})

	r.Any("/headers/", func(c echo.Context) error {
		//Data used for header content is irrelevant here, only header presence is checked
		c.Response().Writer.Header().Set("content-type", "text/plain")
		c.Response().Writer.Header().Set("content-length", "42")
		c.Response().Writer.Header().Set("content-language", "en-US")

		return c.String(http.StatusOK, "Hello, headers!")
	})

	initDatadog()
	r.Start(":7777")
}
