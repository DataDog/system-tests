import os
import psutil
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


def pid(request):
    return HttpResponse(os.getpid())

def commandline(request):
    # Get the current process ID
    pid = os.getpid()

    # Get the process by PID
    process = psutil.Process(pid)

    # Get the command line
    cmdline = process.cmdline()

    return HttpResponse(" ".join(cmdline))

urlpatterns = [
    path("", index),
    path("crashme", crashme),
    path("pid", pid),
    path("commandline", commandline),
]
