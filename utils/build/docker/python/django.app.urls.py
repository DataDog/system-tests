# pages/urls.py
from django.urls import path
from django.http import HttpResponse
from ddtrace import tracer


tracer.trace("init.service").finish()


def hello_world(request):
    return HttpResponse("Hello, World!")


def sample_rate(request, i):
    return HttpResponse("OK")


def waf(request, url=""):
    return HttpResponse("Hello, World!")


urlpatterns = [
    path("", hello_world),
    path("sample_rate_route/<int:i>", sample_rate),
    path("waf", waf),
    path("waf/", waf),
    path("waf/<url>", waf),
    path("params/<appscan_fingerprint>", waf)
]
