# pages/urls.py
import json

import requests
from ddtrace import tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from iast import (
    weak_cipher,
    weak_cipher_secure_algorithm,
    weak_hash,
    weak_hash_duplicates,
    weak_hash_multiple,
    weak_hash_secure_algorithm,
)

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

tracer.trace("init.service").finish()


def hello_world(request):
    return HttpResponse("Hello, World!")


def sample_rate(request, i):
    return HttpResponse("OK")


_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@csrf_exempt
def waf(request, *args, **kwargs):
    if "tag_value" in kwargs:
        appsec_trace_utils.track_custom_event(
            tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": kwargs["tag_value"]}
        )
        if kwargs["tag_value"].startswith("payload_in_response_body") and request.method == "POST":
            return HttpResponse(json.dumps({"payload": dict(request.POST)}), content_type="application/json")
        return HttpResponse("Value tagged", status=int(kwargs["status_code"]), headers=request.GET.dict())
    return HttpResponse("Hello, World!")


def headers(request):
    response = HttpResponse("OK")
    response["Content-Language"] = "en-US"
    return response


def status_code(request, *args, **kwargs):
    return HttpResponse("OK, probably", status=int(request.GET.get("code", "200")))


def identify(request):
    set_user(
        tracer,
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return HttpResponse("OK")


def users(request):
    user_id = request.GET["user"]
    set_user(
        tracer,
        user_id=user_id,
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return HttpResponse("OK")


def identify_propagate(request):
    set_user(
        tracer,
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
        propagate=True,
    )
    return HttpResponse("OK")


def view_weak_hash_multiple_hash(request):
    weak_hash_multiple()
    return HttpResponse("OK")


def view_weak_hash_secure_algorithm(request):
    result = weak_hash_secure_algorithm()
    return HttpResponse("OK")


def view_weak_hash_md5_algorithm(request):
    result = weak_hash()
    return HttpResponse("OK")


def view_weak_hash_deduplicate(request):
    result = weak_hash_duplicates()
    return HttpResponse("OK")


def view_weak_cipher_insecure(request):
    weak_cipher()
    return HttpResponse("OK")


def view_weak_cipher_secure(request):
    weak_cipher_secure_algorithm()
    return HttpResponse("OK")


def view_insecure_cookies_insecure(request):
    res = HttpResponse("OK")
    res.set_cookie("insecure", "cookie", secure=False)
    return res


def view_insecure_cookies_secure(request):
    res = HttpResponse("OK")
    res.set_cookie("secure2", "value", secure=True, httponly=True, samesite="Strict")
    return res


def view_insecure_cookies_empty(request):
    res = HttpResponse("OK")
    res.set_cookie("secure3", "", secure=True, httponly=True, samesite="Strict")
    return res


def view_nohttponly_cookies_insecure(request):
    res = HttpResponse("OK")
    res.set_cookie("insecure", "cookie", secure=True, httponly=False, samesite="Strict")
    return res


def view_nohttponly_cookies_secure(request):
    res = HttpResponse("OK")
    res.set_cookie("secure2", "value", secure=True, httponly=True, samesite="Strict")
    return res


def view_nohttponly_cookies_empty(request):
    res = HttpResponse("OK")
    res.set_cookie("secure3", "", secure=True, httponly=True, samesite="Strict")
    return res


def view_nosamesite_cookies_insecure(request):
    res = HttpResponse("OK")
    res.set_cookie("insecure", "cookie", secure=True, httponly=True, samesite="None")
    return res


def view_nosamesite_cookies_secure(request):
    res = HttpResponse("OK")
    res.set_cookie("secure2", "value", secure=True, httponly=True, samesite="Strict")
    return res


def view_nosamesite_cookies_empty(request):
    res = HttpResponse("OK")
    res.set_cookie("secure3", "", secure=True, httponly=True, samesite="Strict")
    return res


@csrf_exempt
def view_sqli_insecure(request):
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    sql = "SELECT * FROM IAST_USER WHERE USERNAME = " + username + " AND PASSWORD = " + password

    with connection.cursor() as cursor:
        cursor.execute(sql)
    return HttpResponse("OK")


@csrf_exempt
def view_sqli_secure(request):
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    sql = "SELECT * FROM IAST_USER WHERE USERNAME = ? AND PASSWORD = ?"

    with connection.cursor() as cursor:
        cursor.execute(sql, (username, password))
    return HttpResponse("OK")


def _sink_point(table="user", id="1"):
    sql = "SELECT * FROM " + table + " WHERE id = '" + id + "'"
    with connection.cursor() as cursor:
        cursor.execute(sql)


@csrf_exempt
def view_iast_source_body(request):
    # TODO: migrate to a django rest framework view with request.data
    import json

    table = json.loads(request.body).get("name")
    user = json.loads(request.body).get("value")
    _sink_point(table=table, id=user)
    return HttpResponse("OK")


def view_iast_source_cookie_name(request):
    param = [key for key in request.COOKIES.keys() if key == "user"]
    _sink_point(id=param[0])
    return HttpResponse("OK")


def view_iast_source_cookie_value(request):
    table = request.COOKIES.get("table")
    _sink_point(table=table)
    return HttpResponse("OK")


def view_iast_source_header_name(request):
    param = [key for key in request.headers.keys() if key == "User"]
    # param = [key for key in request.META.keys() if key == "HTTP_USER"]
    _sink_point(id=param[0])
    return HttpResponse("OK")


def view_iast_source_header_value(request):
    table = request.META.get("HTTP_TABLE")
    _sink_point(table=table)
    return HttpResponse("OK")


def view_iast_source_parametername(request):
    if request.method == "GET":
        param = [key for key in request.GET.keys() if key == "user"]
        _sink_point(id=param[0])
    elif request.method == "POST":
        param = [key for key in request.POST.keys() if key == "user"]
        _sink_point(id=param[0])
    return HttpResponse("OK")


@csrf_exempt
def view_iast_source_parameter(request):
    if request.method == "GET":
        table = request.GET.get("table")
        _sink_point(table=table[0])
    elif request.method == "POST":
        table = request.POST.get("table")
        _sink_point(table=table[0])

    return HttpResponse("OK")


def make_distant_call(request):
    # curl localhost:7777/make_distant_call?url=http%3A%2F%2Fweblog%3A7777 | jq

    url = request.GET.get("url")
    response = requests.get(url)

    result = {
        "url": url,
        "status_code": response.status_code,
        "request_headers": dict(response.request.headers),
        "response_headers": dict(response.headers),
    }

    return JsonResponse(result)


_TRACK_METADATA = {
    "metadata0": "value0",
    "metadata1": "value1",
}


_TRACK_USER = "system_tests_user"


def track_user_login_success_event(request):
    appsec_trace_utils.track_user_login_success_event(tracer, user_id=_TRACK_USER, metadata=_TRACK_METADATA)
    return HttpResponse("OK")


def track_user_login_failure_event(request):
    appsec_trace_utils.track_user_login_failure_event(
        tracer, user_id=_TRACK_USER, exists=True, metadata=_TRACK_METADATA,
    )
    return HttpResponse("OK")


_TRACK_CUSTOM_EVENT_NAME = "system_tests_event"


def track_custom_event(request):
    appsec_trace_utils.track_custom_event(tracer, event_name=_TRACK_CUSTOM_EVENT_NAME, metadata=_TRACK_METADATA)
    return HttpResponse("OK")


def read_file(request):
    if "file" not in request.GET:
        return HttpResponseBadRequest("Please provide a file parameter")

    filename = request.GET["file"]

    with open(filename, "r") as f:
        return HttpResponse(f.read())


VALUE_STORED = ""


@csrf_exempt
def set_value(request, value, code=200):
    """set_value entry point.
    First parameter after the /set_value/ is used to set internal value
    Second optional parameter is to set status response code
    Any query parameter is used to set header reponse
    """

    global VALUE_STORED
    VALUE_STORED = value
    return HttpResponse("Value set", status=code, headers=request.GET.dict())


def get_value(request):
    return HttpResponse(VALUE_STORED)


urlpatterns = [
    path("", hello_world),
    path("sample_rate_route/<int:i>", sample_rate),
    path("waf", waf),
    path("waf/", waf),
    path("waf/<url>", waf),
    path("params/<appscan_fingerprint>", waf),
    path("tag_value/<str:tag_value>/<int:status_code>", waf),
    path("headers", headers),
    path("status", status_code),
    path("identify", identify),
    path("users", users),
    path("identify-propagate", identify_propagate),
    path("iast/insecure_hashing/multiple_hash", view_weak_hash_multiple_hash),
    path("iast/insecure_hashing/test_secure_algorithm", view_weak_hash_secure_algorithm),
    path("iast/insecure_hashing/test_md5_algorithm", view_weak_hash_md5_algorithm),
    path("iast/insecure_hashing/deduplicate", view_weak_hash_deduplicate),
    path("iast/insecure_cipher/test_insecure_algorithm", view_weak_cipher_insecure),
    path("iast/insecure_cipher/test_secure_algorithm", view_weak_cipher_secure),
    path("iast/insecure-cookie/test_insecure", view_insecure_cookies_insecure),
    path("iast/insecure-cookie/test_secure", view_insecure_cookies_secure),
    path("iast/insecure-cookie/test_empty_cookie", view_insecure_cookies_empty),
    path("iast/no-httponly-cookie/test_insecure", view_nohttponly_cookies_insecure),
    path("iast/no-httponly-cookie/test_secure", view_nohttponly_cookies_secure),
    path("iast/no-httponly-cookie/test_empty_cookie", view_nohttponly_cookies_empty),
    path("iast/no-samesite-cookie/test_insecure", view_nosamesite_cookies_insecure),
    path("iast/no-samesite-cookie/test_secure", view_nosamesite_cookies_secure),
    path("iast/no-samesite-cookie/test_empty_cookie", view_nosamesite_cookies_empty),
    path("iast/sqli/test_secure", view_sqli_secure),
    path("iast/sqli/test_insecure", view_sqli_insecure),
    path("iast/source/body/test", view_iast_source_body),
    path("iast/source/cookiename/test", view_iast_source_cookie_name),
    path("iast/source/cookievalue/test", view_iast_source_cookie_value),
    path("iast/source/headername/test", view_iast_source_header_name),
    path("iast/source/header/test", view_iast_source_header_value),
    path("iast/source/parametername/test", view_iast_source_parametername),
    path("iast/source/parameter/test", view_iast_source_parameter),
    path("make_distant_call", make_distant_call),
    path("user_login_success_event", track_user_login_success_event),
    path("user_login_failure_event", track_user_login_failure_event),
    path("custom_event", track_custom_event),
    path("read_file", read_file),
]
