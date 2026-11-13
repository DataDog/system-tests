import asyncio
import base64
import contextlib
import json
import logging
import operator
import os
import random
import secrets
import shlex
import sqlite3
import subprocess
import sys
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import ddtrace
import psycopg2
import stripe
import xmltodict
from aiohttp import web
from ddtrace._trace.pin import Pin
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace.appsec import track_user_sdk
from ddtrace.constants import MANUAL_DROP_KEY, MANUAL_KEEP_KEY
from ddtrace.contrib.aiohttp import trace_app
from ddtrace.contrib.trace_utils import set_user
from ddtrace.openfeature import DataDogProvider
from ddtrace.trace import tracer
from iast import (
    weak_cipher,
    weak_cipher_secure_algorithm,
    weak_hash,
    weak_hash_duplicates,
    weak_hash_multiple,
    weak_hash_secure_algorithm,
)
from jinja2 import Template
from openfeature import api
from openfeature.evaluation_context import EvaluationContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

tracer.trace("init.service").finish()

# Configure Stripe client for testing
stripe.api_key = "sk_FAKE"
stripe.api_base = "http://internal_server:8089"

# Configure OpenFeature for FFE
api.set_provider(DataDogProvider())
openfeature_client = api.get_client()

POSTGRES_CONFIG = {
    "host": "postgres",
    "port": "5433",
    "user": "system_tests_user",
    "password": "system_tests",
    "dbname": "system_tests_dbname",
}

_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"
_TRACK_CUSTOM_EVENT_NAME = "system_tests_event"
_TRACK_METADATA = {"metadata0": "value0", "metadata1": "value1"}
_TRACK_USER = "system_tests_user"

MAGIC_SESSION_KEY = "random_session_id"

# aiohttp has no built-in session support: logged-in users are kept in memory, keyed by a cookie
_LOGIN_SESSION_COOKIE = "aiohttp_session"
_LOGIN_SESSIONS: dict[str, str] = {}

_DB_USER = {
    "test": ("social-security-id", "test", "1234", "testuser@ddog.com"),
    "testuuid": ("591dc126-8431-4d0f-9509-b23318d3dce4", "testuuid", "1234", "testuseruuid@ddog.com"),
}

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

routes = web.RouteTableDef()


@web.middleware
async def log_not_found_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        return await handler(request)
    except web.HTTPNotFound:
        logger.critical("request %s failed with 404", request.url)
        raise


@web.middleware
async def user_tracking_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Automatically track users from session cookies."""
    user_id = _LOGIN_SESSIONS.get(request.cookies.get(_LOGIN_SESSION_COOKIE, ""))
    session_id = request.cookies.get("session_id")
    if user_id or session_id:
        with contextlib.suppress(Exception):
            track_user_sdk.track_user(login=user_id, user_id=user_id, session_id=session_id, _auto=True)
    return await handler(request)


async def _read_body_params(request: web.Request) -> dict[str, Any]:
    """Return the body parameters of a form or json request."""
    if request.content_type == "application/json":
        return await request.json()
    return dict(await request.post())


def _status_response(code: int, text: str) -> web.Response:
    if code == HTTPStatus.NO_CONTENT:
        return web.Response(status=code)
    return web.Response(text=text, status=code)


### Core endpoints


@routes.get("/")
@routes.post("/")
@routes.options("/")
async def root(request: web.Request) -> web.Response:
    return web.Response(text="Hello world!\n")


@routes.get("/healthcheck")
async def healthcheck(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "library": {"name": "python", "version": ddtrace.__version__}})


@routes.get("/headers")
async def headers(request: web.Request) -> web.Response:
    return web.Response(text="Hello headers!\n", headers={"Content-Type": "text", "Content-Language": "en-US"})


@routes.get("/html")
async def html(request: web.Request) -> web.Response:
    return web.Response(
        text="""<!DOCTYPE html>
<html>
<head>
    <title>Hello</title>
</head>
<body>
    <h1>Hello</h1>
</body>
</html>""",
        content_type="text/html",
    )


@routes.get("/status")
async def status(request: web.Request) -> web.Response:
    return _status_response(int(request.query.get("code", "200")), "OK, probably")


@routes.get("/stats-unique")
async def stats_unique(request: web.Request) -> web.Response:
    return _status_response(int(request.query.get("code", "200")), "OK, probably")


@routes.get("/sample_rate_route/{i}")
async def sample_rate(request: web.Request) -> web.Response:
    return web.Response(text="OK")


@routes.route("*", "/waf")
@routes.route("*", "/waf/")
@routes.route("*", "/waf/{path:.+}")
@routes.route("*", "/params/{path}")
async def waf(request: web.Request) -> web.Response:
    return web.Response(text="Hello world!\n")


@routes.get("/tag_value/{tag_value}/{status_code:\\d+}")
@routes.post("/tag_value/{tag_value}/{status_code:\\d+}")
@routes.options("/tag_value/{tag_value}/{status_code:\\d+}")
async def tag_value(request: web.Request) -> web.Response:
    value = request.match_info["tag_value"]
    code = int(request.match_info["status_code"])
    appsec_trace_utils.track_custom_event(
        tracer,
        event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME,
        metadata={"value": value},
    )
    response_headers = dict(request.query)
    if request.method == "POST" and value.startswith("payload_in_response_body"):
        body = await _read_body_params(request)
        return web.Response(
            text=json.dumps({"payload": body}),
            status=code,
            headers={"Content-Type": "application/json", **response_headers},
        )
    return web.Response(text="Value tagged", status=code, headers=response_headers)


@routes.get("/set_cookie")
async def set_cookie(request: web.Request) -> web.Response:
    return web.Response(text="OK", headers={"Set-Cookie": f"{request.query['name']}={request.query['value']}"})


@routes.get("/read_file")
async def read_file(request: web.Request) -> web.Response:
    file = request.query.get("file")
    if file is None:
        return web.Response(text="Please provide a file parameter", status=400)
    return web.Response(text=Path(file).read_text())


@routes.get("/createextraservice")
async def create_extra_service(request: web.Request) -> web.Response:
    service_name = request.query.get("serviceName", "")
    if service_name:
        Pin.override(aiohttp, service=service_name)
    return web.Response(text="OK")


@routes.get("/resource_renaming/{path:.*}")
async def resource_renaming(request: web.Request) -> web.Response:
    return web.Response(text="ok")


def write_thread_context(path: str) -> dict[str, str] | None:
    span = tracer.current_span()
    if span is None:
        return None

    with Path(path).open("w") as f:
        f.write("system-tests thread context sharing")

    return {"trace_id": str(span.trace_id), "span_id": str(span.span_id)}


async def write_thread_context_after_yield(path: str) -> dict[str, str] | None:
    # Force a task switch before the syscall so child-task context restoration is validated.
    await asyncio.sleep(0)
    return write_thread_context(path)


@routes.get("/security/thread_context_sharing")
async def thread_context_sharing(request: web.Request) -> web.Response:
    result = await asyncio.create_task(write_thread_context_after_yield(request.query["path"]))
    if result is None:
        return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)
    return web.json_response(result)


### API Security


@routes.get("/api_security_sampling/{i}")
async def api_security_sampling(request: web.Request) -> web.Response:
    return web.Response(text="OK")


@routes.get("/api_security/sampling/{status_code:\\d+}")
async def api_security_sampling_status(request: web.Request) -> web.Response:
    return _status_response(int(request.match_info["status_code"]), "Hello!")


@routes.get("/api_security/multi-params-in-segment/{id:[^/.]+}.{format}")
async def api_security_multi_params_in_segment(request: web.Request) -> web.Response:
    return web.Response(text="ok")


@routes.get("/api_security/optional-params/{id:[^/.]+}")
@routes.get("/api_security/optional-params/{id:[^/.]+}.{format}")
async def api_security_optional_params(request: web.Request) -> web.Response:
    return web.Response(text="ok")


### User events and identification


@routes.get("/identify")
async def identify(request: web.Request) -> web.Response:
    set_user(
        tracer,
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return web.Response(text="OK")


@routes.get("/identify-propagate")
async def identify_propagate(request: web.Request) -> web.Response:
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
    return web.Response(text="OK")


@routes.get("/users")
async def users(request: web.Request) -> web.Response:
    set_user(
        tracer,
        user_id=request.query["user"],
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return web.Response(text="OK")


@routes.get("/user_login_success_event")
async def user_login_success_event(request: web.Request) -> web.Response:
    appsec_trace_utils.track_user_login_success_event(
        tracer,
        user_id=_TRACK_USER,
        login=_TRACK_USER,
        metadata=_TRACK_METADATA,
    )
    return web.Response(text="OK")


@routes.get("/user_login_failure_event")
async def user_login_failure_event(request: web.Request) -> web.Response:
    appsec_trace_utils.track_user_login_failure_event(
        tracer,
        user_id=_TRACK_USER,
        exists=True,
        metadata=_TRACK_METADATA,
    )
    return web.Response(text="OK")


@routes.post("/user_login_success_event_v2")
async def user_login_success_event_v2(request: web.Request) -> web.Response:
    json_data = await request.json()
    track_user_sdk.track_login_success(
        login=json_data.get("login"),
        user_id=json_data.get("user_id"),
        metadata=json_data.get("metadata"),
    )
    return web.Response(text="OK")


@routes.post("/user_login_failure_event_v2")
async def user_login_failure_event_v2(request: web.Request) -> web.Response:
    json_data = await request.json()
    track_user_sdk.track_login_failure(
        login=json_data.get("login"),
        exists=json_data.get("exists") != "false",
        metadata=json_data.get("metadata"),
    )
    return web.Response(text="OK")


@routes.get("/custom_event")
async def custom_event(request: web.Request) -> web.Response:
    appsec_trace_utils.track_custom_event(tracer, event_name=_TRACK_CUSTOM_EVENT_NAME, metadata=_TRACK_METADATA)
    return web.Response(text="OK")


def _check_user(username: str | None, password: str | None) -> tuple[bool, str | None]:
    if username in _DB_USER:
        return (_DB_USER[username][2] == password), _DB_USER[username][0]
    return False, None


@routes.get("/login")
@routes.post("/login")
async def login(request: web.Request) -> web.Response:
    form = await request.post()
    username = form.get("username")
    password = form.get("password")
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Basic "):
        username, password = base64.b64decode(authorization[6:]).decode().split(":", 1)

    success, user_id = _check_user(username, password)
    session_token = None
    if success:
        appsec_trace_utils.track_user_login_success_event(
            tracer,
            user_id=user_id,
            login_events_mode="auto",
            login=username,
        )
        session_token = secrets.token_hex(16)
        _LOGIN_SESSIONS[session_token] = user_id
    elif user_id:
        appsec_trace_utils.track_user_login_failure_event(
            tracer,
            user_id=user_id,
            exists=True,
            login_events_mode="auto",
            login=username,
        )
    else:
        appsec_trace_utils.track_user_login_failure_event(
            tracer,
            user_id=username,
            exists=False,
            login_events_mode="auto",
            login=username,
        )

    sdk_event = request.query.get("sdk_event")
    if sdk_event:
        sdk_user = request.query.get("sdk_user")
        sdk_mail = request.query.get("sdk_mail")
        if sdk_event == "success":
            appsec_trace_utils.track_user_login_success_event(tracer, user_id=sdk_user, email=sdk_mail, login=sdk_user)
            success = True
        elif sdk_event == "failure":
            appsec_trace_utils.track_user_login_failure_event(
                tracer,
                user_id=sdk_user,
                email=sdk_mail,
                exists=request.query.get("sdk_user_exists") == "true",
                login=sdk_user,
            )

    if not success:
        return web.Response(text="login failure", status=401)
    response = web.Response(text="OK")
    if session_token:
        response.set_cookie(_LOGIN_SESSION_COOKIE, session_token)
    return response


@routes.post("/signup")
async def signup(request: web.Request) -> web.Response:
    form = await request.post()
    username = form.get("username")
    password = form.get("password")
    if not username or not password:
        return web.Response(text="signup failure: username and password required", status=400)
    track_user_sdk.track_signup(user_id="new-user", login=username)
    return web.Response(text="OK")


@routes.get("/session/new")
async def session_new(request: web.Request) -> web.Response:
    response = web.Response(text=MAGIC_SESSION_KEY)
    response.set_cookie("session_id", MAGIC_SESSION_KEY)
    return response


@routes.get("/session/user")
async def session_user(request: web.Request) -> web.Response:
    user = request.query.get("sdk_user", "")
    if user and request.cookies.get("session_id", "") == MAGIC_SESSION_KEY:
        appsec_trace_utils.track_user_login_success_event(tracer, user_id=user, session_id=f"session_{user}")
    return web.Response(text="OK")


### Exploit prevention


async def _retrieve_rasp_arg(request: web.Request, key: str) -> Any:  # noqa: ANN401
    if request.method == "GET":
        return request.query.get(key)
    if not request.can_read_body:
        return None
    content_type = request.content_type
    if content_type == "application/json":
        return (await request.json()).get(key)
    if content_type == "application/xml":
        param = xmltodict.parse(await request.text()).get(key)
        if key == "command" and isinstance(param, dict):
            param = param.get("cmd")
        return param
    if content_type in ("application/x-www-form-urlencoded", "multipart/form-data"):
        return (await request.post()).get(key)
    return None


@routes.get("/rasp/lfi")
@routes.post("/rasp/lfi")
async def rasp_lfi(request: web.Request) -> web.Response:
    file = await _retrieve_rasp_arg(request, "file")
    if file is None:
        return web.Response(text="missing file parameter", status=400)
    try:
        with open(file, "rb") as f_in:  # noqa: PTH123
            f_in.seek(0, os.SEEK_END)
            return web.Response(text=f"{file} open with {f_in.tell()} bytes")
    except OSError as e:
        return web.Response(text=f"{file} could not be open: {e!r}")


@routes.get("/rasp/multiple")
@routes.post("/rasp/multiple")
async def rasp_multiple(request: web.Request) -> web.Response:
    file1 = await _retrieve_rasp_arg(request, "file1")
    file2 = await _retrieve_rasp_arg(request, "file2")
    if file1 is None or file2 is None:
        return web.Response(text="missing file1 or file2 parameter", status=400)
    lengths = []
    for file in [file1, file2, "../etc/passwd"]:
        try:
            with open(file, "rb") as f_in:  # noqa: PTH123
                f_in.seek(0, os.SEEK_END)
                lengths.append(f_in.tell())
        except Exception:  # noqa: BLE001
            lengths.append(0)
    return web.Response(text=f"files open with {lengths} bytes")


@routes.get("/rasp/ssrf")
@routes.post("/rasp/ssrf")
async def rasp_ssrf(request: web.Request) -> web.Response:
    domain = await _retrieve_rasp_arg(request, "domain")
    if domain is None:
        return web.Response(text="missing domain parameter", status=400)
    url = f"http://{domain}"
    try:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1)) as session,
            session.get(url) as response,
        ):
            content = await response.read()
            return web.Response(text=f"url {url} open with {len(content)} bytes")
    except Exception as e:  # noqa: BLE001
        return web.Response(text=f"url {url} could not be open: {e!r}")


@routes.get("/rasp/sqli")
@routes.post("/rasp/sqli")
async def rasp_sqli(request: web.Request) -> web.Response:
    user_id = await _retrieve_rasp_arg(request, "user_id")
    if user_id is None:
        return web.Response(text="missing user_id parameter", status=400)
    try:
        db = sqlite3.connect(":memory:")
        cursor = db.execute(f"SELECT * FROM users WHERE id='{user_id}'")  # noqa: S608
        return web.Response(text=f"DB request with {len(list(cursor))} results")
    except Exception as e:  # noqa: BLE001
        return web.Response(text=f"DB request failure: {e!r}", status=201)


@routes.get("/rasp/shi")
@routes.post("/rasp/shi")
async def rasp_shi(request: web.Request) -> web.Response:
    list_dir = await _retrieve_rasp_arg(request, "list_dir")
    if list_dir is None:
        return web.Response(text="missing list_dir parameter", status=400)
    try:
        command = f"ls {list_dir}"
        res = os.system(command)  # noqa: S605
        return web.Response(text=f"Shell command [{command}] with result: {res}")
    except Exception as e:  # noqa: BLE001
        return web.Response(text=f"Shell command failure: {e!r}", status=201)


@routes.get("/rasp/cmdi")
@routes.post("/rasp/cmdi")
async def rasp_cmdi(request: web.Request) -> web.Response:
    cmd = await _retrieve_rasp_arg(request, "command")
    if cmd is None:
        return web.Response(text="missing command parameter", status=400)
    try:
        res = subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
        return web.Response(text=f"Exec command [{cmd}] with result: {res}")
    except Exception as e:  # noqa: BLE001
        return web.Response(text=f"Exec command [{cmd}] failure: {e!r}", status=201)


### HTTP clients and downstream requests


async def _distant_call_result(url: str, response: aiohttp.ClientResponse) -> dict[str, Any]:
    return {
        "url": url,
        "status_code": response.status,
        "request_headers": dict(response.request_info.headers),
        "response_headers": dict(response.headers),
    }


@routes.get("/make_distant_call")
async def make_distant_call(request: web.Request) -> web.Response:
    url = request.query["url"]
    # The method is configurable so semantic-convention tests can drive a non-standard verb
    # through the client instrumentation. Matches the nodejs express weblog.
    method = request.query.get("method", "GET")
    async with aiohttp.ClientSession() as session, session.request(method, url) as response:
        return web.json_response(await _distant_call_result(url, response))


@routes.get("/trace/manual_keep_drop")
async def trace_manual_keep_drop(request: web.Request) -> web.Response:
    decision = request.query.get("decision", "")
    if decision not in ("keep", "drop"):
        return web.Response(text="decision must be keep or drop", status=400)

    span = tracer.current_span()
    span.set_tag(MANUAL_KEEP_KEY if decision == "keep" else MANUAL_DROP_KEY)

    # Call downstream so that tests can assert on the sampling decision that gets propagated
    url = "http://localhost:7777/"
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        return web.json_response(await _distant_call_result(url, response))


async def _request_return_headers() -> bytes:
    async with aiohttp.ClientSession() as session, session.get("http://localhost:7777/returnheaders") as response:
        return await response.read()


@routes.route("*", "/requestdownstream")
@routes.route("*", "/requestdownstream/")
async def request_downstream(request: web.Request) -> web.Response:
    return web.Response(body=await _request_return_headers())


@routes.route("*", "/vulnerablerequestdownstream")
@routes.route("*", "/vulnerablerequestdownstream/")
async def vulnerable_request_downstream(request: web.Request) -> web.Response:
    weak_hash()
    return web.Response(body=await _request_return_headers())


@routes.route("*", "/returnheaders")
@routes.route("*", "/returnheaders/")
async def return_headers(request: web.Request) -> web.Response:
    return web.json_response(dict(request.headers))


async def _external_request(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict[str, Any]:
    try:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
            session.request(method, url, headers=headers, data=body) as response,
        ):
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "payload": json.loads(await response.text()),
            }
    except Exception as e:  # noqa: BLE001
        return {"status": None, "error": repr(e)}


@routes.get("/external_request")
@routes.post("/external_request")
@routes.put("/external_request")
async def external_request(request: web.Request) -> web.Response:
    queries = dict(request.query)
    status = queries.pop("status", "200")
    url_extra = queries.pop("url_extra", "")
    body = await request.read() or None
    if body:
        queries["Content-Type"] = request.headers.get("Content-Type") or "application/json"
    url = f"http://internal_server:8089/mirror/{status}{url_extra}"
    return web.json_response(await _external_request(request.method, url, queries, body))


@routes.get("/external_request/redirect")
async def external_request_redirect(request: web.Request) -> web.Response:
    queries = dict(request.query)
    url = f"http://internal_server:8089/redirect?totalRedirects={queries.get('totalRedirects', '0')}"
    return web.json_response(await _external_request("GET", url, queries, None))


### Database


@routes.get("/dbm")
async def dbm(request: web.Request) -> web.Response:
    integration = request.query["integration"]
    operation = request.query.get("operation", "")
    if integration != "psycopg":
        return web.Response(text=f"Integration is not supported: {integration}", status=406)
    cursor = psycopg2.connect(**POSTGRES_CONFIG).cursor()
    if operation == "execute":
        cursor.execute("select 'blah'")
        return web.Response(text="OK")
    if operation == "executemany":
        cursor.executemany("select %s", (("blah",), ("moo",)))
        return web.Response(text="OK")
    return web.Response(text=f"Cursor method is not supported: {operation}", status=406)


### IAST


@routes.get("/iast/insecure_hashing/multiple_hash")
async def iast_weak_hash_multiple(request: web.Request) -> web.Response:
    weak_hash_multiple()
    return web.Response(text="OK")


@routes.get("/iast/insecure_hashing/test_secure_algorithm")
async def iast_weak_hash_secure_algorithm(request: web.Request) -> web.Response:
    weak_hash_secure_algorithm()
    return web.Response(text="OK")


@routes.get("/iast/insecure_hashing/test_md5_algorithm")
async def iast_weak_hash_md5_algorithm(request: web.Request) -> web.Response:
    weak_hash()
    return web.Response(text="OK")


@routes.get("/iast/insecure_hashing/deduplicate")
async def iast_weak_hash_deduplicate(request: web.Request) -> web.Response:
    weak_hash_duplicates()
    return web.Response(text="OK")


@routes.get("/iast/insecure_cipher/test_insecure_algorithm")
async def iast_weak_cipher_insecure(request: web.Request) -> web.Response:
    weak_cipher()
    return web.Response(text="OK")


@routes.get("/iast/insecure_cipher/test_secure_algorithm")
async def iast_weak_cipher_secure(request: web.Request) -> web.Response:
    weak_cipher_secure_algorithm()
    return web.Response(text="OK")


def _cookie_response(name: str, value: str, *, secure: bool, httponly: bool, samesite: str) -> web.Response:
    response = web.Response(text="OK")
    response.set_cookie(name, value, secure=secure, httponly=httponly, samesite=samesite)
    return response


@routes.get("/iast/insecure-cookie/test_insecure")
async def iast_insecure_cookie_insecure(request: web.Request) -> web.Response:
    return _cookie_response("insecure", "cookie", secure=False, httponly=False, samesite="None")


@routes.get("/iast/insecure-cookie/test_secure")
async def iast_insecure_cookie_secure(request: web.Request) -> web.Response:
    return _cookie_response("secure3", "value", secure=True, httponly=True, samesite="Strict")


@routes.get("/iast/insecure-cookie/test_empty_cookie")
async def iast_insecure_cookie_empty(request: web.Request) -> web.Response:
    return _cookie_response("secure3", "", secure=True, httponly=True, samesite="Strict")


@routes.get("/iast/no-httponly-cookie/test_insecure")
async def iast_no_httponly_cookie_insecure(request: web.Request) -> web.Response:
    return _cookie_response("insecure", "cookie", secure=True, httponly=False, samesite="Strict")


@routes.get("/iast/no-httponly-cookie/test_secure")
async def iast_no_httponly_cookie_secure(request: web.Request) -> web.Response:
    return _cookie_response("secure3", "value", secure=True, httponly=True, samesite="Strict")


@routes.get("/iast/no-httponly-cookie/test_empty_cookie")
async def iast_no_httponly_cookie_empty(request: web.Request) -> web.Response:
    return _cookie_response("secure3", "", secure=True, httponly=True, samesite="Strict")


@routes.get("/iast/no-samesite-cookie/test_insecure")
async def iast_no_samesite_cookie_insecure(request: web.Request) -> web.Response:
    return _cookie_response("insecure", "cookie", secure=True, httponly=True, samesite="None")


@routes.get("/iast/no-samesite-cookie/test_secure")
async def iast_no_samesite_cookie_secure(request: web.Request) -> web.Response:
    return _cookie_response("secure3", "value", secure=True, httponly=True, samesite="Strict")


@routes.get("/iast/no-samesite-cookie/test_empty_cookie")
async def iast_no_samesite_cookie_empty(request: web.Request) -> web.Response:
    return _cookie_response("secure3", "", secure=True, httponly=True, samesite="None")


@routes.post("/iast/header_injection/test_insecure")
async def iast_header_injection_insecure(request: web.Request) -> web.Response:
    header_value = (await request.post()).get("test")
    response = web.Response(text="OK")
    # label iast_header_injection
    response.headers["Header-Injection"] = header_value
    return response


@routes.post("/iast/header_injection/test_secure")
async def iast_header_injection_secure(request: web.Request) -> web.Response:
    header_value = (await request.post()).get("test")
    response = web.Response(text="OK")
    # label iast_header_injection
    response.headers["Vary"] = header_value
    return response


@routes.post("/iast/unvalidated_redirect/test_insecure_redirect")
async def iast_unvalidated_redirect_insecure(request: web.Request) -> web.Response:
    location = (await request.post()).get("location")
    raise web.HTTPFound(location)


@routes.post("/iast/unvalidated_redirect/test_insecure_header")
async def iast_unvalidated_redirect_insecure_header(request: web.Request) -> web.Response:
    location = (await request.post()).get("location")
    return web.Response(text="OK", headers={"Location": location})


@routes.post("/iast/unvalidated_redirect/test_secure_redirect")
async def iast_unvalidated_redirect_secure(request: web.Request) -> web.Response:
    location = "http://dummy.location.com"
    raise web.HTTPFound(location)


@routes.post("/iast/unvalidated_redirect/test_secure_header")
async def iast_unvalidated_redirect_secure_header(request: web.Request) -> web.Response:
    return web.Response(text="OK", headers={"Location": "http://dummy.location.com"})


def _sink_point_sqli(table: str = "user", id: str = "1") -> None:  # noqa: A002
    sql = "SELECT * FROM " + table + " WHERE id = '" + id + "'"  # noqa: S608
    cursor = psycopg2.connect(**POSTGRES_CONFIG).cursor()
    with contextlib.suppress(psycopg2.errors.UndefinedColumn):
        cursor.execute(sql)


def _sink_point_path_traversal(tainted_str: str = "user") -> None:
    with contextlib.suppress(Exception), open(tainted_str) as f:  # noqa: PTH123
        f.read()


@routes.post("/iast/source/body/test")
async def iast_source_body(request: web.Request) -> web.Response:
    json_body = await request.json()
    _sink_point_path_traversal(json_body["value"])
    return web.Response(text="OK")


@routes.get("/iast/source/cookiename/test")
async def iast_source_cookie_name(request: web.Request) -> web.Response:
    param = [key for key in request.cookies if key == "table"]
    if param:
        _sink_point_path_traversal(tainted_str=param[0])
        return web.Response(text="OK")
    return web.Response(text="KO")


@routes.get("/iast/source/cookievalue/test")
async def iast_source_cookie_value(request: web.Request) -> web.Response:
    _sink_point_path_traversal(tainted_str=request.cookies.get("table", "undefined"))
    return web.Response(text="OK")


@routes.get("/iast/source/header/test")
async def iast_source_header_value(request: web.Request) -> web.Response:
    _sink_point_path_traversal(tainted_str=request.headers.get("table", "undefined"))
    return web.Response(text="OK")


@routes.get("/iast/source/headername/test")
async def iast_source_header_name(request: web.Request) -> web.Response:
    table = next(key for key in request.headers if key.lower() == "user")
    _sink_point_path_traversal(tainted_str=table)
    return web.Response(text="OK")


@routes.get("/iast/source/parametername/test")
@routes.post("/iast/source/parametername/test")
async def iast_source_parameter_name(request: web.Request) -> web.Response:
    params = request.query if request.method == "GET" else await request.post()
    param = [key for key in params if key == "user"]
    if param:
        _sink_point_path_traversal(param[0])
        return web.Response(text="OK")
    return web.Response(text="KO")


@routes.get("/iast/source/parameter/test")
@routes.post("/iast/source/parameter/test")
async def iast_source_parameter(request: web.Request) -> web.Response:
    table = request.query.get("table")
    if table is None:
        table = (await request.post()).get("table")
    _sink_point_sqli(table=table)
    return web.Response(text="OK")


@routes.get("/iast/source/path/test")
async def iast_source_path(request: web.Request) -> web.Response:
    _sink_point_path_traversal(tainted_str=request.path)
    return web.Response(text="OK")


@routes.get("/iast/source/path_parameter/test/{table}")
async def iast_source_path_parameter(request: web.Request) -> web.Response:
    _sink_point_path_traversal(tainted_str=request.match_info["table"])
    return web.Response(text="OK")


@routes.get("/iast/sampling-by-route-method-count/{id}")
@routes.post("/iast/sampling-by-route-method-count/{id}")
async def iast_sampling_by_route_method(request: web.Request) -> web.Response:
    """Report the same path traversal vulnerability from 15 different code locations.

    The IAST sampling algorithm should only report the first 2 vulnerabilities per request and skip the rest,
    then report the next 2 vulnerabilities in subsequent requests.
    Each open() must stay inline, on its own line, to be a distinct vulnerability location.
    """
    param = request.query.get("param") if request.query else (await request.post()).get("param")
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    return web.Response(text="OK")


@routes.get("/iast/sampling-by-route-method-count-2/{id}")
async def iast_sampling_by_route_method_2(request: web.Request) -> web.Response:
    """Report the same vulnerability as iast_sampling_by_route_method, on a second route and for GET only."""
    param = request.query.get("param")
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    with contextlib.suppress(Exception):
        open(param).close()  # noqa: PTH123
    return web.Response(text="OK")


@routes.post("/iast/path_traversal/test_insecure")
async def iast_path_traversal_insecure(request: web.Request) -> web.Response:
    path = (await request.post()).get("path")
    with contextlib.suppress(FileExistsError):
        os.mkdir(path)  # noqa: PTH102
    return web.Response(text="OK")


@routes.post("/iast/path_traversal/test_secure")
async def iast_path_traversal_secure(request: web.Request) -> web.Response:
    path = (await request.post()).get("path")
    root_dir = "/home/usr/secure_folder/"
    if os.path.commonprefix((os.path.realpath(path), root_dir)) == root_dir:
        open(path).close()  # noqa: PTH123
    return web.Response(text="OK")


@routes.post("/iast/sqli/test_insecure")
async def iast_sqli_insecure(request: web.Request) -> web.Response:
    form = await request.post()
    sql = "SELECT * FROM users WHERE username='" + form["username"] + "' AND password='" + form["password"] + "'"  # noqa: S608
    cursor = psycopg2.connect(**POSTGRES_CONFIG).cursor()
    with contextlib.suppress(psycopg2.errors.UndefinedTable):
        cursor.execute(sql)
    return web.Response(text="OK")


@routes.post("/iast/sqli/test_secure")
async def iast_sqli_secure(request: web.Request) -> web.Response:
    form = await request.post()
    sql = "SELECT * FROM users WHERE username=%s AND password=%s"
    cursor = psycopg2.connect(**POSTGRES_CONFIG).cursor()
    with contextlib.suppress(psycopg2.errors.UndefinedTable):
        cursor.execute(sql, (form["username"], form["password"]))
    return web.Response(text="OK")


@routes.post("/iast/ssrf/test_insecure")
async def iast_ssrf_insecure(request: web.Request) -> web.Response:
    url = (await request.post()).get("url")
    with contextlib.suppress(Exception):
        async with aiohttp.ClientSession() as session, session.get(str(url)) as response:
            await response.read()
    return web.Response(text="OK")


@routes.post("/iast/ssrf/test_secure")
async def iast_ssrf_secure(request: web.Request) -> web.Response:
    url = (await request.post()).get("url")
    # Validate the URL and enforce whitelist
    allowed_domains = ["example.com", "api.example.com", "www.datadoghq.com"]
    if urlparse(str(url)).hostname not in allowed_domains:
        return web.Response(text="Forbidden", status=403)
    with contextlib.suppress(Exception):
        async with aiohttp.ClientSession() as session, session.get("https://www.datadoghq.com") as response:
            await response.read()
    return web.Response(text="OK")


@routes.get("/iast/stack_trace_leak/test_insecure")
async def iast_stack_trace_leak_insecure(request: web.Request) -> web.Response:
    return web.Response(
        text="""
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
        """,
    )


@routes.get("/iast/stack_trace_leak/test_secure")
async def iast_stack_trace_leak_secure(request: web.Request) -> web.Response:
    return web.Response(text="OK")


@routes.get("/iast/weak_randomness/test_insecure")
async def iast_weak_randomness_insecure(request: web.Request) -> web.Response:
    _ = random.randint(1, 100)  # noqa: S311
    return web.Response(text="OK")


@routes.get("/iast/weak_randomness/test_secure")
async def iast_weak_randomness_secure(request: web.Request) -> web.Response:
    _ = random.SystemRandom().randint(1, 100)
    return web.Response(text="OK")


@routes.post("/iast/cmdi/test_insecure")
async def iast_cmdi_insecure(request: web.Request) -> web.Response:
    cmd = (await request.post()).get("cmd")
    os.system(cmd + " -la /")  # noqa: S605
    return web.Response(text="OK")


@routes.post("/iast/cmdi/test_secure")
async def iast_cmdi_secure(request: web.Request) -> web.Response:
    cmd = (await request.post()).get("cmd")
    os.system(shlex.quote(cmd) + " -la /")  # noqa: S605
    return web.Response(text="OK")


@routes.post("/iast/code_injection/test_insecure")
async def iast_code_injection_insecure(request: web.Request) -> web.Response:
    _ = eval((await request.post()).get("code"))  # noqa: S307
    return web.Response(text="OK")


@routes.post("/iast/code_injection/test_secure")
async def iast_code_injection_secure(request: web.Request) -> web.Response:
    code = (await request.post()).get("code")
    ops = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
    if len(code) != 3 or code[1] not in ops:  # noqa: PLR2004
        msg = "Invalid expression"
        raise ValueError(msg)
    a, op, b = code
    _ = ops[op](float(a), float(b))
    return web.Response(text="OK")


@routes.post("/iast/xss/test_insecure")
async def iast_xss_insecure(request: web.Request) -> web.Response:
    param = (await request.post()).get("param")
    return web.Response(text=Template("<p>{{ param|safe }}</p>").render(param=param), content_type="text/html")


@routes.post("/iast/xss/test_secure")
async def iast_xss_secure(request: web.Request) -> web.Response:
    param = (await request.post()).get("param")
    return web.Response(text=Template("<p>{{ param }}</p>").render(param=param), content_type="text/html")


### Feature flags


@routes.post("/ffe")
async def ffe(request: web.Request) -> web.Response:
    """OpenFeature evaluation endpoint."""
    body = await request.json()
    flag = body.get("flag")
    variation_type = body.get("variationType")
    default_value = body.get("defaultValue")
    context = EvaluationContext(targeting_key=body.get("targetingKey"), attributes=body.get("attributes", {}))

    if variation_type == "BOOLEAN":
        value = openfeature_client.get_boolean_value(flag, default_value, context)
    elif variation_type == "STRING":
        value = openfeature_client.get_string_value(flag, default_value, context)
    elif variation_type in ("INTEGER", "NUMERIC"):
        value = openfeature_client.get_integer_value(flag, default_value, context)
    elif variation_type == "JSON":
        value = openfeature_client.get_object_value(flag, default_value, context)
    else:
        return web.json_response({"error": f"Unknown variation type: {variation_type}"}, status=400)

    return web.json_response({"value": value})


### Stripe


@routes.post("/stripe/create_checkout_session")
async def stripe_create_checkout_session(request: web.Request) -> web.Response:
    try:
        result = stripe.checkout.Session.create(**(await request.json()))
        return web.json_response(dict(result))
    except Exception as e:  # noqa: BLE001
        return web.json_response({"error": str(e)}, status=500)


@routes.post("/stripe/create_payment_intent")
async def stripe_create_payment_intent(request: web.Request) -> web.Response:
    try:
        result = stripe.PaymentIntent.create(**(await request.json()))
        return web.json_response(dict(result))
    except Exception as e:  # noqa: BLE001
        return web.json_response({"error": str(e)}, status=500)


@routes.post("/stripe/webhook")
async def stripe_webhook(request: web.Request) -> web.Response:
    try:
        event = stripe.Webhook.construct_event(
            await request.read(),
            request.headers.get("Stripe-Signature"),
            "whsec_FAKE",
        )
        return web.json_response(event.data.object)
    except Exception as e:  # noqa: BLE001
        return web.json_response({"error": str(e)}, status=403)


def make_app() -> web.Application:
    application = web.Application(middlewares=[log_not_found_middleware, user_tracking_middleware])
    # The aiohttp server is not instrumented automatically: trace_app inserts the
    # tracing middleware first, so the middlewares above run inside the request span.
    trace_app(application)
    application.add_routes(routes)
    # RouteTableDef has no helper for TRACE (it looks up a missing router.add_trace)
    application.router.add_route("TRACE", "/external_request", external_request)
    return application


app = make_app()
