package main

import (
	"net/http"

	"github.com/gin-gonic/gin"

	gintrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/gin-gonic/gin"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	r := gin.New()
	r.Use(gintrace.Middleware("weblog"))

	r.Any("/", func(ctx *gin.Context) {
		ctx.Writer.WriteHeader(http.StatusOK)
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

	r.Any("/headers/", func(ctx *gin.Context) {
		//Data used for header content is irrelevant here, only header presence is checked
		ctx.Writer.Header().Set("content-type", "text/plain")
		ctx.Writer.Header().Set("content-length", "42")
		ctx.Writer.Header().Set("content-language", "en-US")
		ctx.Writer.Write([]byte("Hello, headers!"))
	})

	initDatadog()
	http.ListenAndServe(":7777", r)
}
