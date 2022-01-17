package main

import (
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/ext"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func initDatadog() {
	span := tracer.StartSpan("init.service")
	defer span.Finish()
	span.SetTag("whip", "done")
	// avoid the default 0 priority not be removed by the sampler which removes
	// every trace whose span priorities are <= 0 - this feature is configured
	// by the agent and cannot be configured so far
	span.SetTag(ext.SamplingPriority, ext.PriorityUserKeep)
}
