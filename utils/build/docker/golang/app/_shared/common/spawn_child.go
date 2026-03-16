package common

import (
	"fmt"
	"net/http"
	"os/exec"
	"strconv"
	"strings"
)

// SpawnChild handles GET /spawn_child for telemetry session ID header tests.
// Go does not support fork; returns 400 when fork=true. Otherwise uses exec.
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

	crash := crashStr == "true"
	script := fmt.Sprintf("sleep %d", sleep)
	if crash {
		script += " && kill -SEGV $$"
	} else {
		script += " && exit 0"
	}
	cmd := exec.Command("sh", "-c", script)
	_ = cmd.Run()
	status := 0
	if cmd.ProcessState != nil {
		status = cmd.ProcessState.ExitCode()
	}
	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte(fmt.Sprintf("Child process exited with status %d", status)))
}
