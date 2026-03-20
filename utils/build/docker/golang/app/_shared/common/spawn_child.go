package common

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

// RunAsChildIfRequested checks if the process was re-exec'd in child mode.
// If so, it initializes the tracer, sleeps, optionally crashes, then exits.
// Call this at the top of main() before any other initialization.
func RunAsChildIfRequested() {
	sleepStr := os.Getenv("DD_SYSTEM_TEST_CHILD_SLEEP")
	if sleepStr == "" {
		return
	}
	sleep, _ := strconv.Atoi(sleepStr)
	crash := os.Getenv("DD_SYSTEM_TEST_CHILD_CRASH") == "true"

	tracer.Start()
	time.Sleep(time.Duration(sleep) * time.Second)
	tracer.Stop()

	if crash {
		syscall.Kill(syscall.Getpid(), syscall.SIGSEGV)
	}
	os.Exit(0)
}

// SpawnChild handles GET /spawn_child for telemetry session ID header tests.
// Go does not support fork; returns 400 when fork=true. Otherwise re-execs
// the current binary in child mode, which initializes dd-trace-go and emits
// its own telemetry. The SDK propagates DD_ROOT_GO_SESSION_ID via the process
// environment so that child processes inherit the root session ID automatically.
func SpawnChild(w http.ResponseWriter, r *http.Request) {
	sleepStr := r.URL.Query().Get("sleep")
	crashStr := strings.ToLower(r.URL.Query().Get("crash"))
	forkStr := strings.ToLower(r.URL.Query().Get("fork"))

	sleep, err := strconv.Atoi(sleepStr)
	if err != nil || sleep < 0 {
		http.Error(w, "sleep required", http.StatusBadRequest)
		return
	}
	if crashStr != "true" && crashStr != "false" {
		http.Error(w, "crash required (boolean)", http.StatusBadRequest)
		return
	}
	if forkStr != "true" && forkStr != "false" {
		http.Error(w, "fork required (boolean)", http.StatusBadRequest)
		return
	}
	if forkStr == "true" {
		http.Error(w, "fork not supported", http.StatusBadRequest)
		return
	}

	cmd := exec.Command(os.Args[0])
	cmd.Env = append(os.Environ(),
		"DD_SYSTEM_TEST_CHILD_SLEEP="+sleepStr,
		"DD_SYSTEM_TEST_CHILD_CRASH="+crashStr,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	_ = cmd.Run()
	status := 0
	if cmd.ProcessState != nil {
		status = cmd.ProcessState.ExitCode()
	}
	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte(fmt.Sprintf("Child process exited with status %d", status)))
}
