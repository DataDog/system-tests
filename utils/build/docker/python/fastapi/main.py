import json
import typing

import psycopg2
import requests
from ddtrace import Pin, tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
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

app = FastAPI()

_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@app.get("/", response_class=PlainTextResponse)
async def root():
    return "Hello, World!"


@app.get("/sample_rate_route/<i>", response_class=PlainTextResponse)
async def sample_rate(i):
    return "OK"


@app.get("/waf", response_class=PlainTextResponse)
@app.post("/waf", response_class=PlainTextResponse)
@app.options("/waf", response_class=PlainTextResponse)
@app.get("/waf/", response_class=PlainTextResponse)
@app.post("/waf/", response_class=PlainTextResponse)
@app.options("/waf/", response_class=PlainTextResponse)
async def waf():
    return "Hello, World!\n"


@app.get("/waf/<path>", response_class=PlainTextResponse)
@app.post("/waf/<path>", response_class=PlainTextResponse)
@app.options("/waf/<path>", response_class=PlainTextResponse)
@app.get("/params/<path>", response_class=PlainTextResponse)
@app.post("/params/<path>", response_class=PlainTextResponse)
@app.options("/params/<path>", response_class=PlainTextResponse)
async def waf_params(path):
    return "Hello, World!\n"


@app.get("/tag_value/<tag_value>/<status_code>", response_class=PlainTextResponse)
@app.options("/tag_value/<tag_value>/<status_code>", response_class=PlainTextResponse)
async def tag_value(tag_value: str, status_code: int, request: Request):
    appsec_trace_utils.track_custom_event(
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    return PlainTextResponse("Value tagged", status_code=status_code, headers=request.query_params)


@app.post("/tag_value/<tag_value>/<status_code>")
async def tag_value_post(tag_value: str, status_code: int, request: Request):
    appsec_trace_utils.track_custom_event(
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    if tag_value.startswith(payload_in_response_body):
        raw_body = await request.body()
        json_body = json.loads(raw_body)
        return JSONResponse({"payload": json_body}, status_code=status_code, headers=request.query_params)
    return PlainTextResponse("Value tagged", status_code=status_code, headers=request.query_params)


@app.get("/read_file", response_class=PlainTextResponse)
async def read_file(file: typing.Optional[str] = None):
    if file is None:
        return PlainTextResponse("Please provide a file parameter", status_code=400)
    with open(file, "r") as f:
        return f.read()


@app.get("/headers")
async def headers():
    return PlainTextResponse("OK", headers={"Content-Language": "en-US"})


@app.get("/status")
async def status_code(code: int = 200):
    return PlainTextResponse("OK, probably", status_code=code)


@app.get("/make_distant_call")
def make_distant_call(url: str):
    response = requests.get(url)

    result = {
        "url": url,
        "status_code": response.status_code,
        "request_headers": dict(response.request.headers),
        "response_headers": dict(response.headers),
    }

    return result


@app.get("/identify", response_class=PlainTextResponse)
def identify():
    set_user(
        tracer,
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return "OK"


@app.get("/identify-propagate", response_class=PlainTextResponse)
def identify_propagate():
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
    return "OK"


@app.get("/users", response_class=PlainTextResponse)
def users(user: str):
    set_user(
        tracer,
        user_id=user,
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return "OK"


@app.get("/dbm", response_class=PlainTextResponse)
def dbm(integration: str, operation: str = ""):
    if integration == "psycopg":
        postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = postgres_db.cursor()
        if operation == "execute":
            cursor.execute("select 'blah'")
            return "OK"
        elif operation == "executemany":
            cursor.executemany("select %s", (("blah",), ("moo",)))
            return "OK"
        return PlainTextResponse(f"Cursor method is not supported: {operation}", status_code=406)

    return PlainTextResponse(f"Integration is not supported: {integration}", status_code=406)


@app.get("/iast/insecure_hashing/multiple_hash", response_class=PlainTextResponse)
def view_weak_hash_multiple_hash():
    weak_hash_multiple()
    return "OK"


@app.get("/iast/insecure_hashing/test_secure_algorithm", response_class=PlainTextResponse)
def view_weak_hash_secure_algorithm():
    result = weak_hash_secure_algorithm()
    return "OK"


@app.get("/iast/insecure_hashing/test_md5_algorithm", response_class=PlainTextResponse)
def view_weak_hash_md5_algorithm():
    result = weak_hash()
    return "OK"


@app.get("/iast/insecure_hashing/deduplicate", response_class=PlainTextResponse)
def view_weak_hash_deduplicate():
    weak_hash_duplicates()
    return "OK"


@app.get("/iast/insecure_cipher/test_insecure_algorithm", response_class=PlainTextResponse)
def view_weak_cipher_insecure():
    weak_cipher()
    return "OK"


@app.get("/iast/insecure_cipher/test_secure_algorithm", response_class=PlainTextResponse)
def view_weak_cipher_secure():
    weak_cipher_secure_algorithm()
    return "OK"
