// Child process for /spawn_child endpoint. Initializes dd-trace-go so that
// telemetry (app-started, heartbeats, app-closed) is emitted with its own
// runtime_id. If DD_ROOT_GO_SESSION_ID is set in the environment (injected by
// the parent), the SDK uses it for the DD-Root-Session-ID header.
//
// Usage: child <sleep_seconds> <crash>
package main

import (
	"fmt"
	"os"
	"strconv"
	"syscall"
	"time"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintf(os.Stderr, "usage: child <sleep_seconds> <crash>\n")
		os.Exit(1)
	}

	sleep, err := strconv.Atoi(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid sleep: %v\n", err)
		os.Exit(1)
	}
	crash := os.Args[2] == "true"

	tracer.Start()

	time.Sleep(time.Duration(sleep) * time.Second)

	if crash {
		tracer.Stop()
		syscall.Kill(syscall.Getpid(), syscall.SIGSEGV)
	}

	tracer.Stop()
}
