import os
import signal
import sys
import time

from django.http import HttpResponse
from django.urls import path


def handle_sigterm(signo, sf):
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


filepath, extension = os.path.splitext(__file__)
ROOT_URLCONF = os.path.basename(filepath)
DEBUG = False
SECRET_KEY = "fdsfdasfa"
ALLOWED_HOSTS = ["*"]


def index(request):
    return HttpResponse("test")


def crashme(request):
    import ctypes

    ctypes.string_at(0)


def fork_and_crash(request):
    pid = os.fork()
    if pid > 0:
        # Parent process
        _, status = os.waitpid(pid, 0)  # Wait for the child process to exit
        return HttpResponse(f"Child process {pid} exited with status {status}")
    if pid == 0:
        # Child process
        time.sleep(5)  # don't crash immediately or the telemetry forwarder leaves a zombie behind
        crashme(request)
        return HttpResponse("Nobody should see this")


def child_pids(request):
    current_pid = os.getpid()
    child_pids = []

    # Iterate over all directories in /proc to look for PIDs
    try:
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                status_path = f"/proc/{pid}/status"
                try:
                    with open(status_path, "r") as status_file:
                        for line in status_file:
                            if line.startswith("PPid:"):
                                ppid = int(line.split()[1])
                                if ppid == current_pid:
                                    child_pids.append(pid)
                                break
                except (FileNotFoundError, PermissionError):
                    # Process might have terminated or we don't have permission
                    continue

        # Format the response to include the list of child PIDs
        response_content = ", ".join(child_pids)
        return HttpResponse(response_content, content_type="text/plain")
    except Exception as e:
        return HttpResponse(f"Error: {e!s}", status=500, content_type="text/plain")


def zombies(request):
    zombie_processes = []

    # Iterate over all directories in /proc to look for PIDs
    try:
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                status_path = f"/proc/{pid}/status"
                try:
                    with open(status_path, "r") as status_file:
                        state = None
                        name = None
                        ppid = None
                        for line in status_file:
                            if line.startswith("State:"):
                                state = line.split()[1]
                            elif line.startswith("Name:"):
                                name = line.split()[1]
                            elif line.startswith("PPid:"):
                                ppid = line.split()[1]
                            if state and name and ppid:
                                break
                        # Check if the process state is 'Z' (zombie)
                        if state == "Z":
                            zombie_processes.append(f"{name} (PID: {pid}, PPID: {ppid})")
                except (FileNotFoundError, PermissionError):
                    # Process might have terminated or we don't have permission
                    continue

        # Format the response to include the list of zombie processes with their names, PIDs, and PPIDs
        response_content = ", ".join(zombie_processes)
        return HttpResponse(response_content, content_type="text/plain")
    except Exception as e:
        return HttpResponse(f"Error: {e!s}", status=500, content_type="text/plain")


urlpatterns = [
    path("", index),
    path("crashme", crashme),
    path("fork_and_crash", fork_and_crash),
    path("child_pids", child_pids),
    path("zombies", zombies),
]
