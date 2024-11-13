import os
import signal
import subprocess
import sys

from django.http import HttpResponse
from django.urls import path


def handle_sigterm(signo, sf):
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


filepath, extension = os.path.splitext(__file__)
ROOT_URLCONF = os.path.basename(filepath)
DEBUG = True
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
    elif pid == 0:
        # Child process
        crashme(request)
        return HttpResponse("Nobody should see this")


def child_pids(request):
    current_pid = os.getpid()
    ps_command = ["ps", "--ppid", str(current_pid), "--no-headers"]

    result = subprocess.run(ps_command, capture_output=True, text=True, check=True)

    return HttpResponse(result.stdout)


urlpatterns = [
    path("", index),
    path("crashme", crashme),
    path("fork_and_crash", fork_and_crash),
    path("child_pids", child_pids),
]
