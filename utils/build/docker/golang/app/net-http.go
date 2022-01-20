package main

import (
	"net/http"

	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	mux := NewWeblogMux()
	initDatadog()
	http.ListenAndServe(":7777", mux)
}
