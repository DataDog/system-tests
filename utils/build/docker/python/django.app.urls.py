# pages/urls.py
import requests
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


def distributed_http(request):
    end_hello = requests.get("http://weblog:7777/distributed-http-end")
    return HttpResponse(end_hello.content)


def distributed_http_end(request):
    return HttpResponse("Hello, Distributed Http World!")


urlpatterns = [
    path("", hello_world),
    path("distributed-http", distributed_http),
    path("distributed-http-end", distributed_http_end),
    path("sample_rate_route/<int:i>", sample_rate),
    path("waf", waf),
    path("waf/", waf),
    path("waf/<url>", waf),
    path("params/<appscan_fingerprint>", waf),
]
