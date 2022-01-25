package main

import (
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/ext"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func initDatadog() {
	span := tracer.StartSpan("init.service")
	defer span.Finish()
	span.SetTag(ext.SamplingPriority, ext.PriorityUserKeep)
	span.SetTag("whip", "done")
}
