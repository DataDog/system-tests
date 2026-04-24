import os
import signal
import sys
import types

from django.http import HttpRequest, HttpResponse
from django.urls import path


def handle_sigterm(signo: int, sf: types.FrameType | None) -> None:
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


filepath, extension = os.path.splitext(__file__)
ROOT_URLCONF = os.path.basename(filepath)
DEBUG = False
SECRET_KEY = "fdsfdasfa"
ALLOWED_HOSTS = ["*"]


def index(request: HttpRequest):
    import ddtrace

    if ddtrace.__version__ != "1.12.0":
        print(
            "Assertion failure: unexpected ddtrace version received. Got %r when expecting '1.12.0'"
            % ddtrace.__version__
        )
        # Hard exit so traces aren't flushed.
        os._exit(1)
    return HttpResponse("test")


urlpatterns = [
    path("", index),
]
