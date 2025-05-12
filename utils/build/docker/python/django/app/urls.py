# pages/urls.py
import base64
import json
import os
import random
import shlex
import subprocess
import xmltodict
import sys
import http.client
import urllib.request

import boto3
import django
import requests
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.utils.safestring import mark_safe
from moto import mock_aws
import urllib3
from iast import (
    weak_cipher,
    weak_cipher_secure_algorithm,
    weak_hash,
    weak_hash_duplicates,
    weak_hash_multiple,
    weak_hash_secure_algorithm,
)

import ddtrace
from ddtrace import patch_all

try:
    from ddtrace.appsec import track_user_sdk
except ImportError:
    # fallback for when the new SDK is not available
    class TUS:
        def track_login_success(self, *args, **kwargs):
            pass

        def track_login_failure(self, *args, **kwargs):
            pass

        def track_custom_event(self, *args, **kwargs):
            pass

    track_user_sdk = TUS()

try:
    from ddtrace.trace import Pin, tracer
except ImportError:
    from ddtrace import tracer, Pin


patch_all(urllib3=True)

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

tracer.trace("init.service").finish()


from app.models import CustomUser

# creating users at start
for username, email, passwd, last_name, user_id in [
    ("test", "testuser@ddog.com", "1234", "test", "social-security-id"),
    ("testuuid", "testuseruuid@ddog.com", "1234", "testuuid", "591dc126-8431-4d0f-9509-b23318d3dce4"),
]:
    try:
        if not CustomUser.objects.filter(id=user_id).exists():
            CustomUser.objects.create_user(username, email, passwd, last_name=last_name, id=user_id)
    except Exception as e:
        pass


def hello_world(request):
    return HttpResponse("Hello, World!")


def api_security_sampling_status(request, *args, **kwargs):
    return HttpResponse("Hello!", status=int(kwargs["status_code"]))


def api_security_sampling(request, i):
    return HttpResponse("OK")


def sample_rate(request, i):
    return HttpResponse("OK")


_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@csrf_exempt
def healthcheck(request):
    result = {
        "status": "ok",
        "library": {
            "name": "python",
            "version": ddtrace.__version__,
        },
    }

    return HttpResponse(json.dumps(result), content_type="application/json")


@csrf_exempt
def waf(request, *args, **kwargs):
    if "tag_value" in kwargs:
        track_user_sdk.track_custom_event(
            event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME,
            metadata={"value": kwargs["tag_value"]},
        )
        if kwargs["tag_value"].startswith("payload_in_response_body") and request.method == "POST":
            return HttpResponse(
                json.dumps({"payload": dict(request.POST)}),
                content_type="application/json",
                status=int(kwargs["status_code"]),
                headers=request.GET.dict(),
            )
        return HttpResponse(
            "Value tagged",
            status=int(kwargs["status_code"]),
            headers=request.GET.dict(),
        )
    return HttpResponse("Hello, World!")


@csrf_exempt
def return_headers(request, *args, **kwargs):
    headers = {}
    for k, v in request.headers.items():
        headers[k] = v
    return HttpResponse(json.dumps(headers))


@csrf_exempt
def request_downstream(request, *args, **kwargs):
    # Propagate the received headers to the downstream service
    http = urllib3.PoolManager()
    # Sending a GET request and getting back response as HTTPResponse object.
    response = http.request("GET", "http://localhost:7777/returnheaders")
    return HttpResponse(response.data)


@csrf_exempt
def vulnerable_request_downstream(request, *args, **kwargs):
    weak_hash()
    # Propagate the received headers to the downstream service
    http = urllib3.PoolManager()
    # Sending a GET request and getting back response as HTTPResponse object.
    response = http.request("GET", "http://localhost:7777/returnheaders")
    return HttpResponse(response.data)


@csrf_exempt
def set_cookie(request):
    res = HttpResponse("OK")
    res.headers["Set-Cookie"] = f"{request.GET.get('name')}={request.GET.get('value')}"
    return res


### BEGIN EXPLOIT PREVENTION


def retrieve_arg(request, key: str):
    data = None
    if request.method == "GET":
        data = request.GET.get(key)
    elif request.method == "POST":
        try:
            data = (request.POST or json.loads(request.body)).get(key)
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            if data is None:
                data = xmltodict.parse(request.body).get(key)
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass
    return data


@csrf_exempt
def rasp_lfi(request, *args, **kwargs):
    file = retrieve_arg(request, "file")
    if file is None:
        return HttpResponse("missing file parameter", status=400)
    try:
        with open(file, "rb") as f_in:
            f_in.seek(0, os.SEEK_END)
            return HttpResponse(f"{file} open with {f_in.tell()} bytes")
    except OSError as e:
        return HttpResponse(f"{file} could not be open: {e!r}")


@csrf_exempt
def rasp_multiple(request, *args, **kwargs):
    file1 = retrieve_arg(request, "file1")
    file2 = retrieve_arg(request, "file2")
    if file1 is None or file2 is None:
        return HttpResponse("missing file1 or file2 parameter", status=400)
    lengths = []
    for file in [file1, file2, "../etc/passwd"]:
        try:
            with open(file, "rb") as f_in:
                f_in.seek(0, os.SEEK_END)
                lengths.append(f_in.tell())
        except Exception:
            lengths.append(0)
    return HttpResponse(f"files open with {lengths} bytes")


@csrf_exempt
def rasp_ssrf(request, *args, **kwargs):
    domain = retrieve_arg(request, "domain")
    if domain is None:
        return HttpResponse("missing domain parameter", status=400)
    try:
        with urllib.request.urlopen(f"http://{domain}", timeout=1) as url_in:
            return HttpResponse(f"url http://{domain} open with {len(url_in.read())} bytes")
    except http.client.HTTPException as e:
        return HttpResponse(f"url http://{domain} could not be open: {e!r}")


@csrf_exempt
def rasp_sqli(request, *args, **kwargs):
    user_id = retrieve_arg(request, "user_id")
    if user_id is None:
        return HttpResponse("missing user_id parameter", status=400)
    try:
        import sqlite3

        DB = sqlite3.connect(":memory:")
        print(f"SELECT * FROM users WHERE id='{user_id}'")
        cursor = DB.execute(f"SELECT * FROM users WHERE id='{user_id}'")
        print("DB request with {len(list(cursor))} results")
        return HttpResponse(f"DB request with {len(list(cursor))} results")
    except Exception as e:
        print(f"DB request failure: {e!r}", file=sys.stderr)
        return HttpResponse(f"DB request failure: {e!r}", status=201)


@csrf_exempt
def rasp_shi(request, *args, **kwargs):
    list_dir = retrieve_arg(request, "list_dir")
    if list_dir is None:
        return HttpResponse("missing list_dir parameter", status=400)
    try:
        res = os.system(f"ls {list_dir}")
        return HttpResponse(f"Shell command with result: {res}")
    except Exception as e:
        print(f"Shell command failure: {e!r}", file=sys.stderr)
        return HttpResponse(f"Shell command failure: {e!r}", status=201)


@csrf_exempt
def rasp_cmdi(request, *args, **kwargs):
    cmd = None
    if request.method == "GET":
        cmd = request.GET.get("command")
    elif request.method == "POST":
        try:
            cmd = (request.POST or json.loads(request.body)).get("command")
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            if cmd is None:
                cmd = xmltodict.parse(request.body).get("command").get("cmd")
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass

    if cmd is None:
        return HttpResponse("missing command parameter", status=400)
    try:
        res = subprocess.run(cmd, capture_output=True)
        return HttpResponse(f"Exec command [{cmd}] with result: {res}")
    except Exception as e:
        return HttpResponse(f"Shell command [{cmd}] failure: {e!r}", status=201)


### END EXPLOIT PREVENTION


def headers(request):
    response = HttpResponse("OK")
    response["Content-Language"] = "en-US"
    return response


def status_code(request, *args, **kwargs):
    return HttpResponse("OK, probably", status=int(request.GET.get("code", "200")))


def stats_unique(request, *args, **kwargs):
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
    res.set_cookie("insecure", "cookie", secure=False, httponly=True, samesite="Strict")
    return res


def view_insecure_cookies_secure(request):
    res = HttpResponse("OK")
    res.set_cookie("secure2", "value", secure=True, httponly=True, samesite="Strict")
    return res


def view_insecure_cookies_empty(request):
    res = HttpResponse("OK")
    res.set_cookie("insecure", "", secure=False, httponly=True, samesite="Strict")
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
    res.set_cookie("insecure", "", secure=True, httponly=True, samesite="None")
    return res


def view_iast_weak_randomness_insecure(request):
    _ = random.randint(1, 100)
    res = HttpResponse("OK")
    return res


def view_iast_weak_randomness_secure(request):
    random_secure = random.SystemRandom()
    _ = random_secure.randint(1, 100)
    res = HttpResponse("OK")
    return res


@csrf_exempt
def view_cmdi_insecure(request):
    cmd = request.POST.get("cmd", "")
    filename = "tests/appsec/iast/"
    os.system(cmd + " -la " + filename)
    return HttpResponse("OK")


@csrf_exempt
def view_cmdi_secure(request):
    cmd = request.POST.get("cmd", "")
    filename = "tests/appsec/iast/"
    os.system(shlex.quote(cmd) + " -la " + filename)
    return HttpResponse("OK")


@csrf_exempt
def view_iast_path_traversal_insecure(request):
    path = request.POST.get("path", "")
    os.mkdir(path)
    return HttpResponse("OK")


@csrf_exempt
def view_iast_path_traversal_secure(request):
    path = request.POST.get("path", "")
    root_dir = "/home/usr/secure_folder/"

    if os.path.commonprefix((os.path.realpath(path), root_dir)) == root_dir:
        open(path)

    return HttpResponse("OK")


@csrf_exempt
def view_sqli_insecure(request):
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    sql = "SELECT * FROM app_customuser WHERE username = '" + username + "' AND password = '" + password + "'"

    with connection.cursor() as cursor:
        cursor.execute(sql)
    return HttpResponse("OK")


@csrf_exempt
def view_sqli_secure(request):
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    sql = "SELECT * FROM app_customuser WHERE username = %s AND password = %s"

    with connection.cursor() as cursor:
        cursor.execute(sql, (username, password))
    return HttpResponse("OK")


@csrf_exempt
def view_iast_ssrf_insecure(request):
    import requests

    url = request.POST.get("url", "")
    try:
        requests.get(url)
    except Exception:
        pass
    return HttpResponse("OK")


@csrf_exempt
def view_iast_ssrf_secure(request):
    import requests

    try:
        requests.get("https://www.datadog.com")
    except Exception:
        pass

    return HttpResponse("OK")


@csrf_exempt
def view_iast_xss_insecure(request):
    param = request.POST.get("param", "")
    # Validate the URL and enforce whitelist
    return render(request, "index.html", {"param": mark_safe(param)})


@csrf_exempt
def view_iast_xss_secure(request):
    param = request.POST.get("param", "")
    # Validate the URL and enforce whitelist
    return render(request, "index.html", {"param": param})


@csrf_exempt
def view_iast_stacktraceleak_insecure(request):
    return HttpResponse("""
  Traceback (most recent call last):
  File "/usr/local/lib/python3.9/site-packages/some_module.py", line 42, in process_data
    result = complex_calculation(data)
  File "/usr/local/lib/python3.9/site-packages/another_module.py", line 158, in complex_calculation
    intermediate = perform_subtask(data_slice)
  File "/usr/local/lib/python3.9/site-packages/subtask_module.py", line 27, in perform_subtask
    processed = handle_special_case(data_slice)
  File "/usr/local/lib/python3.9/site-packages/special_cases.py", line 84, in handle_special_case
    return apply_algorithm(data_slice, params)
  File "/usr/local/lib/python3.9/site-packages/algorithm_module.py", line 112, in apply_algorithm
    step_result = execute_step(data, params)
  File "/usr/local/lib/python3.9/site-packages/step_execution.py", line 55, in execute_step
    temp = pre_process(data)
  File "/usr/local/lib/python3.9/site-packages/pre_processing.py", line 33, in pre_process
    validated_data = validate_input(data)
  File "/usr/local/lib/python3.9/site-packages/validation.py", line 66, in validate_input
    check_constraints(data)
  File "/usr/local/lib/python3.9/site-packages/constraints.py", line 19, in check_constraints
    raise ValueError("Constraint violation at step 9")
ValueError: Constraint violation at step 9

Lorem Ipsum Foobar
""")


@csrf_exempt
def view_iast_stacktraceleak_secure(request):
    return HttpResponse("OK")


def _sink_point_sqli(table="user", id="1"):
    sql = f"SELECT * FROM {table} WHERE id = '{id}'"
    with connection.cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception:
            pass


def _sink_point_path_traversal(tainted_str="user"):
    try:
        m = open(tainted_str)
        _ = m.read()
    except Exception:
        pass


@csrf_exempt
def view_iast_source_body(request):
    # TODO: migrate to a django rest framework view with request.data
    import json

    table = json.loads(request.body).get("name")
    _sink_point_sqli(table=table)
    return HttpResponse("OK")


def view_iast_source_cookie_name(request):
    param = [key for key in request.COOKIES.keys() if key == "table"]
    _sink_point_path_traversal(param[0])
    return HttpResponse("OK")


def view_iast_source_cookie_value(request):
    table = request.COOKIES.get("table")
    _sink_point_path_traversal(table)
    return HttpResponse("OK")


def view_iast_source_header_name(request):
    param = [key for key in request.headers.keys() if key == "User"]
    # param = [key for key in request.META.keys() if key == "HTTP_USER"]
    _sink_point_sqli(id=param[0])
    return HttpResponse("OK")


def view_iast_source_header_value(request):
    table = request.META.get("HTTP_TABLE")
    _sink_point_sqli(table=table)
    return HttpResponse("OK")


@csrf_exempt
def view_iast_source_parametername(request):
    if request.method == "GET":
        param = [key for key in request.GET.keys() if key == "user"]
        _sink_point_path_traversal(param[0])
    elif request.method == "POST":
        param = [key for key in request.POST.keys() if key == "user"]
        _sink_point_path_traversal(param[0])
    return HttpResponse("OK")


@csrf_exempt
def view_iast_source_parameter(request):
    if request.method == "GET":
        table = request.GET.get("table")
        _sink_point_sqli(table=table[0])
    elif request.method == "POST":
        table = request.POST.get("table")
        _sink_point_sqli(table=table[0])

    return HttpResponse("OK")


@csrf_exempt
def view_iast_source_path(request):
    table = request.path_info
    _sink_point_sqli(table=table[0])

    return HttpResponse("OK")


@csrf_exempt
def view_iast_sampling_by_route_method(request, id):
    if request.GET:
        param_tainted = request.GET.get("param")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
    elif request.POST:
        param_tainted = request.POST.get("param")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
        os.system(f"ls {param_tainted}")
    return HttpResponse("OK", status=200)

def view_iast_sampling_by_route_method_2(request, id):
    param_tainted = request.GET.get("param")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    os.system(f"ls {param_tainted}")
    return HttpResponse("OK", status=200)

@csrf_exempt
def view_iast_source_path_parameter(request, table):
    _sink_point_sqli(table=table)

    return HttpResponse("OK")


@csrf_exempt
def view_iast_header_injection_insecure(request):
    header = request.POST.get("test")
    response = HttpResponse("OK", status=200)
    # label iast_header_injection
    response.headers["Header-Injection"] = header
    return response


@csrf_exempt
def view_iast_header_injection_secure(request):
    header = request.POST.get("test")
    response = HttpResponse("OK", status=200)
    # label iast_header_injection
    response.headers["Vary"] = header
    return response


@csrf_exempt
def view_iast_code_injection_insecure(request):
    code_string = request.POST.get("code")
    _ = eval(code_string)
    return HttpResponse("OK", status=200)


@csrf_exempt
def view_iast_code_injection_secure(request):
    import operator

    def safe_eval(expr):
        ops = {
            "+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "/": operator.truediv,
        }
        if len(expr) != 3 or expr[1] not in ops:
            raise ValueError("Invalid expression")
        a, op, b = expr
        return ops[op](float(a), float(b))

    code_string = request.POST.get("code")
    _ = safe_eval(code_string)
    return HttpResponse("OK", status=200)


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
    track_user_sdk.track_login_success(login=_TRACK_USER, user_id=_TRACK_USER, metadata=_TRACK_METADATA)
    return HttpResponse("OK")


def track_user_login_failure_event(request):
    track_user_sdk.track_login_failure(
        login=_TRACK_USER,
        exists=True,
        user_id=_TRACK_USER,
        metadata=_TRACK_METADATA,
    )
    return HttpResponse("OK")


@csrf_exempt
def login(request):
    from django.contrib.auth import authenticate, login

    is_logged_in = False
    username = request.POST.get("username")
    password = request.POST.get("password")
    sdk_event = request.GET.get("sdk_event")
    authorisation = request.headers.get("Authorization")
    if authorisation:
        username, password = base64.b64decode(authorisation[6:]).decode().split(":")
    user = authenticate(username=username, password=password)
    if user is not None:
        login(request, user)
        is_logged_in = True
    if sdk_event:
        sdk_user = request.GET.get("sdk_user")
        sdk_mail = request.GET.get("sdk_mail")
        sdk_user_exists = request.GET.get("sdk_user_exists")
        if sdk_event == "success":
            track_user_sdk.track_login_success(login=sdk_user, user_id=sdk_user, metadata={"email": sdk_mail})
            is_logged_in = True
        elif sdk_event == "failure":
            track_user_sdk.track_login_failure(login=sdk_user, exists=sdk_user_exists, metadata={"email": sdk_mail})
    if is_logged_in:
        return HttpResponse("OK")
    return HttpResponse("login failure", status=401)


@csrf_exempt
def user_login_success_event(request):
    json_data = json.loads(request.body)
    login = json_data.get("login")
    user_id = json_data.get("user_id")
    metadata = json_data.get("metadata")
    track_user_sdk.track_login_success(login=login, user_id=user_id, metadata=metadata)
    return HttpResponse("OK")


@csrf_exempt
def user_login_failure_event(request):
    json_data = json.loads(request.body)
    login = json_data.get("login")
    exists = False if json_data.get("exists") == "false" else True
    metadata = json_data.get("metadata")
    track_user_sdk.track_login_failure(login=login, exists=exists, metadata=metadata)
    return HttpResponse("OK")


@csrf_exempt
def signup_user(request):
    from app.models import CustomUser

    try:
        username = request.POST.get("username")
        password = request.POST.get("password")
        email = request.POST.get("email")
        user = CustomUser.objects.create_user(username=username, email=email, password=password, id="new-user")
        user.save()
        return HttpResponse("OK")
    except Exception as e:
        return HttpResponse(f"signup failure {e!r}", status=400)


MAGIC_SESSION_KEY = "random_session_id"


def session_new(request):
    request.session.save()
    session_id = request.session.session_key
    return HttpResponse(session_id)


def session_user(request):
    user = request.GET.get("sdk_user", "")
    if user and request.COOKIES.get("session_id", "") == MAGIC_SESSION_KEY:
        # track_user_sdk.track_login_success(user_id=user, session_id=f"session_{user}")
        track_user_sdk.track_login_success(login=user, user_id=user, session_id=f"session_{user}")
    return HttpResponse("OK")


_TRACK_CUSTOM_EVENT_NAME = "system_tests_event"


def track_custom_event(request):
    track_user_sdk.track_custom_event(event_name=_TRACK_CUSTOM_EVENT_NAME, metadata=_TRACK_METADATA)
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


def create_extra_service(request):
    new_service_name = request.GET.get("serviceName", default="")
    if new_service_name:
        Pin.override(django, service=new_service_name)
    return HttpResponse("OK")


def s3_put_object(request):
    bucket = request.GET.get("bucket")
    key = request.GET.get("key")
    body = request.GET.get("key")

    with mock_aws():
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket=bucket)
        response = conn.Bucket(bucket).put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))

        # boto adds double quotes to the ETag
        # so we need to remove them to match what would have done AWS
        result = {
            "result": "ok",
            "object": {
                "e_tag": response.e_tag.replace('"', ""),
            },
        }

    return JsonResponse(result)


def s3_copy_object(request):
    original_bucket = request.GET.get("original_bucket")
    original_key = request.GET.get("original_key")
    body = request.GET.get("original_key")

    copy_source = {
        "Bucket": original_bucket,
        "Key": original_key,
    }

    bucket = request.GET.get("bucket")
    key = request.GET.get("key")

    with mock_aws():
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket=original_bucket)
        conn.Bucket(original_bucket).put_object(Bucket=original_bucket, Key=original_key, Body=body.encode("utf-8"))

        if bucket != original_bucket:
            conn.create_bucket(Bucket=bucket)
        response = conn.Object(bucket, key).copy_from(CopySource=copy_source)

        # boto adds double quotes to the ETag
        # so we need to remove them to match what would have done AWS
        result = {
            "result": "ok",
            "object": {
                "e_tag": response["CopyObjectResult"]["ETag"].replace('"', ""),
            },
        }

    return JsonResponse(result)


def s3_multipart_upload(request):
    bucket = request.GET.get("bucket")
    key = request.GET.get("key")
    body_base = request.GET.get("key")
    body = (body_base + "x" * 15_000_000).encode("utf-8")  # 15MB of padding

    split_index = len(body) // 2
    body_part_1 = body[:split_index]
    body_part_2 = body[split_index:]

    with mock_aws():
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket=bucket)

        multipart_upload = conn.Object(bucket, key).initiate_multipart_upload()
        part_1_response = multipart_upload.Part(1).upload(Body=body_part_1)
        part_2_response = multipart_upload.Part(2).upload(Body=body_part_2)
        response = multipart_upload.complete(
            MultipartUpload={
                "Parts": [
                    {"PartNumber": 1, "ETag": part_1_response["ETag"]},
                    {"PartNumber": 2, "ETag": part_2_response["ETag"]},
                ],
            },
        )

        # boto adds double quotes to the ETag
        # so we need to remove them to match what would have done AWS
        result = {
            "result": "ok",
            "object": {
                "e_tag": response.e_tag.replace('"', ""),
            },
        }

    return JsonResponse(result)


urlpatterns = [
    path("", hello_world),
    path("api_security/sampling/<int:status_code>", api_security_sampling_status),
    path("api_security_sampling/<int:i>", api_security_sampling),
    path("sample_rate_route/<int:i>", sample_rate),
    path("healthcheck", healthcheck),
    path("waf", waf),
    path("waf/", waf),
    path("waf/<url>", waf),
    path("vulnerablerequestdownstream", vulnerable_request_downstream),
    path("vulnerablerequestdownstream/", vulnerable_request_downstream),
    path("requestdownstream", request_downstream),
    path("requestdownstream/", request_downstream),
    path("returnheaders", return_headers),
    path("returnheaders/", return_headers),
    path("set_cookie", set_cookie),
    path("rasp/cmdi", rasp_cmdi),
    path("rasp/lfi", rasp_lfi),
    path("rasp/multiple", rasp_multiple),
    path("rasp/shi", rasp_shi),
    path("rasp/sqli", rasp_sqli),
    path("rasp/ssrf", rasp_ssrf),
    path("params/<appscan_fingerprint>", waf),
    path("tag_value/<str:tag_value>/<int:status_code>", waf),
    path("createextraservice", create_extra_service),
    path("headers", headers),
    path("status", status_code),
    path("stats-unique", stats_unique),
    path("identify", identify),
    path("users", users),
    path("user_login_success_event_v2", user_login_success_event),
    path("user_login_failure_event_v2", user_login_failure_event),
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
    path("iast/cmdi/test_insecure", view_cmdi_insecure),
    path("iast/cmdi/test_secure", view_cmdi_secure),
    path("iast/weak_randomness/test_insecure", view_iast_weak_randomness_insecure),
    path("iast/weak_randomness/test_secure", view_iast_weak_randomness_secure),
    path("iast/path_traversal/test_insecure", view_iast_path_traversal_insecure),
    path("iast/path_traversal/test_secure", view_iast_path_traversal_secure),
    path("iast/ssrf/test_insecure", view_iast_ssrf_insecure),
    path("iast/ssrf/test_secure", view_iast_ssrf_secure),
    path("iast/xss/test_insecure", view_iast_xss_insecure),
    path("iast/xss/test_secure", view_iast_xss_secure),
    path("iast/stack_trace_leak/test_insecure", view_iast_stacktraceleak_insecure),
    path("iast/stack_trace_leak/test_secure", view_iast_stacktraceleak_secure),
    path("iast/source/body/test", view_iast_source_body),
    path("iast/source/cookiename/test", view_iast_source_cookie_name),
    path("iast/source/cookievalue/test", view_iast_source_cookie_value),
    path("iast/source/headername/test", view_iast_source_header_name),
    path("iast/source/header/test", view_iast_source_header_value),
    path("iast/source/parametername/test", view_iast_source_parametername),
    path("iast/source/parameter/test", view_iast_source_parameter),
    path("iast/source/path/test", view_iast_source_path),
    path("iast/source/path_parameter/test/<str:table>", view_iast_source_path_parameter),
    path("iast/header_injection/test_secure", view_iast_header_injection_secure),
    path("iast/code_injection/test_insecure", view_iast_code_injection_insecure),
    path("iast/code_injection/test_secure", view_iast_code_injection_secure),
    path("iast/header_injection/test_insecure", view_iast_header_injection_insecure),
    path("iast/sampling-by-route-method-count/<str:id>/", view_iast_sampling_by_route_method),
    path("iast/sampling-by-route-method-count-2/<str:id>/", view_iast_sampling_by_route_method_2),
    path("make_distant_call", make_distant_call),
    path("user_login_success_event", track_user_login_success_event),
    path("user_login_failure_event", track_user_login_failure_event),
    path("login", login),
    path("session/new", session_new),
    path("session/user", session_user),
    path("signup", signup_user),
    path("custom_event", track_custom_event),
    path("read_file", read_file),
    path("mock_s3/put_object", s3_put_object),
    path("mock_s3/copy_object", s3_copy_object),
    path("mock_s3/multipart_upload", s3_multipart_upload),
]
