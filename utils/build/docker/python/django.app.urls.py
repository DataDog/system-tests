# pages/urls.py
from django.urls import path
from django.http import HttpResponse
from ddtrace import tracer


tracer.trace("init.service").finish()


def hello_world(request):
    return HttpResponse("Hello, World!")


def sample_rate(request, i):
    return HttpResponse("OK")


def waf(request, *args, **kwargs):
    return HttpResponse("Hello, World!")


def headers(request):
    response = HttpResponse("OK")
    response["Content-Language"] = "en-US"
    return response


def status_code(request, *args, **kwargs):
    return HttpResponse("OK, probably", status=int(request.GET.get("code", "200")))


urlpatterns = [
    path("", hello_world),
    path("sample_rate_route/<int:i>", sample_rate),
    path("waf", waf),
    path("waf/", waf),
    path("waf/<url>", waf),
    path("params/<appscan_fingerprint>", waf),
    path("headers", headers),
    path("status", status_code),
]
