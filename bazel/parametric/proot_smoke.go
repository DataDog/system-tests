package main

import (
	"fmt"
	"os"
	"strings"
)

func main() {
	stable, err := os.ReadFile("/etc/datadog-agent/managed/datadog-agent/stable/smoke")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile("/parametric-tracer-logs/smoke.log", stable, 0o644); err != nil {
		panic(err)
	}
	status, err := os.ReadFile("/proc/self/status")
	if err != nil {
		panic(err)
	}
	if !strings.Contains(string(status), "Name:") {
		panic("/proc/self/status has no process name")
	}
	fmt.Print("proot-smoke-ok")
}
