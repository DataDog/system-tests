import os
import signal
import sys

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
    elif pid == 0:
        # Child process
        crashme(request)
        return HttpResponse("Nobody should see this")

def pid(request):
    return HttpResponse(os.getpid())

def commandline(request):
    # Get the current process ID
    pid = os.getpid()

    # Read the command line from /proc filesystem
    with open(f"/proc/{pid}/cmdline", "r") as f:
        cmdline = f.read()

    # The command line arguments are separated by null characters, replace them with spaces
    cmdline = cmdline.replace('\0', ' ')

    return HttpResponse(cmdline.strip())

urlpatterns = [
    path("", index),
    path("crashme", crashme),
    path("fork_and_crash", fork_and_crash),
    path("pid", pid),
    path("commandline", commandline),
]
