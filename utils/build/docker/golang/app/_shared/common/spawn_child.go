package common

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

// SpawnChild handles GET /spawn_child for telemetry session ID header tests.
// Go does not support fork; returns 400 when fork=true. Otherwise spawns a
// child Go process that initializes dd-trace-go and emits its own telemetry.
// The SDK is responsible for propagating DD_ROOT_GO_SESSION_ID via the
// process environment so that child processes inherit the root session ID.
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

	cmd := exec.Command("/app/child", sleepStr, crashStr)
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
