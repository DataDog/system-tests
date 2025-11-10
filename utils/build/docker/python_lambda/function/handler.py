import json
import logging
import os
import sqlite3
import subprocess
import sys
import urllib.parse

from typing import Any

import requests
import xmltodict

from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    APIGatewayHttpResolver,
    ALBResolver,
    LambdaFunctionUrlResolver,
)
from aws_lambda_powertools.utilities.typing.lambda_context import LambdaContext
from aws_lambda_powertools.shared.cookies import Cookie
from aws_lambda_powertools.event_handler import Response

import datadog_lambda
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace.contrib.internal.trace_utils_base import set_user
from ddtrace.trace import tracer


logger = logging.getLogger(__name__)


LAMBDA_EVENT_TYPE = os.environ.get("SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE", "apigateway-rest")
if LAMBDA_EVENT_TYPE == "apigateway-rest":
    app = APIGatewayRestResolver()
elif LAMBDA_EVENT_TYPE == "apigateway-http":
    app = APIGatewayHttpResolver()
elif LAMBDA_EVENT_TYPE == "function-url":
    app = LambdaFunctionUrlResolver()
elif LAMBDA_EVENT_TYPE in ("application-load-balancer", "application-load-balancer-multi"):
    app = ALBResolver()
else:
    logger.error(
        f"Unsupported Lambda event type: {LAMBDA_EVENT_TYPE}",
    )

_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


def version_info():
    return {
        "status": "ok",
        "library": {
            "name": "python_lambda",
            "version": datadog_lambda.__version__,
        },
    }


def get_query_string_parameters() -> dict[str, str] | dict[str, list[str]]:
    return app.current_event.query_string_parameters or app.current_event.multi_value_query_string_parameters


def get_query_string_value(key) -> str:
    if value := app.current_event.get_query_string_value(key):
        return value
    if value := app.current_event.get_multi_value_query_string_values(key):
        return value[0]
    return ""


def get_query_params() -> dict[str, str]:
    if app.current_event.query_string_parameters:
        return {k: v for k, v in app.current_event.query_string_parameters.items()}

    if app.current_event.multi_value_query_string_parameters:
        query_params = {}
        for header, values in app.current_event.multi_value_query_string_parameters.items():
            query_params[header] = values[0]
        return query_params
    return {}


def get_header_value(key) -> str | None:
    if value := app.current_event.headers.get(key):
        return value
    if not app.current_event.multi_value_headers:
        return None
    if value := app.current_event.multi_value_headers.get(key):
        return value[0]
    return None


def retrieve_arg(key: str):
    value = None
    method = app.current_event.http_method
    if method == "GET":
        value = get_query_string_value(key)
    elif method == "POST":
        body = app.current_event.decoded_body
        try:
            data = urllib.parse.parse_qs(body).get(key)
            if data:
                value = data[0]
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                value = data.get(key)
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass
        try:
            if value is None:
                value = xmltodict.parse(body).get(key)
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass
    return value


@app.get("/")
@app.post("/")
@app.route("/", method="OPTIONS")
def root():
    return Response(status_code=200, content_type="text/plain", body="Hello, World!\n")


@app.get("/headers")
def headers():
    return Response(status_code=200, body="OK", content_type="text/plain", headers={"Content-Language": "en-US"})


@app.get("/healthcheck")
def healthcheck_route():
    return Response(
        status_code=200,
        content_type="application/json",
        body=version_info(),
    )


@app.get("/params/<path>")
@app.post("/params/<path>")
@app.route("/params/<path>", method="OPTIONS")
@app.get("/waf")
@app.post("/waf")
@app.get("/waf/")
@app.post("/waf/")
@app.get("/waf/<path>")
@app.post("/waf/<path>")
@app.route("/waf/<path>", method="OPTIONS")
def waf_params(path: str = ""):
    return Response(
        status_code=200,
        content_type="text/plain",
        body="Hello, World!\n",
    )


MAGIC_SESSION_KEY = "random_session_id"


@app.get("/session/new")
def session_new():
    return Response(
        status_code=200,
        content_type="text/plain",
        body=MAGIC_SESSION_KEY,
        cookies=[Cookie(name="session_id", value=MAGIC_SESSION_KEY)],
    )


@app.get("/tag_value/<tag_value>/<status_code>")
@app.route("/tag_value/<tag_value>/<status_code>", method="OPTIONS")
def tag_value(tag_value: str, status_code: int):
    appsec_trace_utils.track_custom_event(  # pyright: ignore[reportPrivateImportUsage]
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    return Response(
        status_code=status_code,
        content_type="text/plain",
        body="Value tagged",
        headers=get_query_string_parameters(),
    )


_TRACK_METADATA = {
    "metadata0": "value0",
    "metadata1": "value1",
}


_TRACK_USER = "system_tests_user"


@app.get("/user_login_success_event")
def track_user_login_success_event():
    appsec_trace_utils.track_user_login_success_event(  # pyright: ignore[reportPrivateImportUsage]
        tracer, user_id=_TRACK_USER, login=_TRACK_USER, metadata=_TRACK_METADATA
    )
    return Response(
        status_code=200,
        content_type="text/plain",
        body="OK",
    )


@app.post("/tag_value/<tag_value>/<status_code>")
def tag_value_post(tag_value: str, status_code: int):
    appsec_trace_utils.track_custom_event(  # pyright: ignore[reportPrivateImportUsage]
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    if tag_value.startswith("payload_in_response_body"):
        # Get form data from the current event
        form_data = urllib.parse.parse_qs(app.current_event.decoded_body)

        return Response(
            status_code=status_code,
            content_type="application/json",
            body={"payload": form_data},
            headers=app.current_event.query_string_parameters or {},
        )
    return Response(
        status_code=status_code,
        content_type="text/plain",
        body="Value tagged",
        headers=app.current_event.query_string_parameters or {},
    )


@app.get("/rasp/lfi")
@app.post("/rasp/lfi")
def rasp_lfi():
    file = retrieve_arg("file")
    if file is None:
        return Response(
            status_code=400,
            content_type="text/plain",
            body="missing file parameter",
        )

    try:
        with open(file, "rb") as file_handle:
            file_handle.seek(0, os.SEEK_END)
            size = file_handle.tell()
        message = f"{file} open with {size} bytes"
    except OSError as exc:
        message = f"{file} could not be open: {exc!r}"

    return Response(
        status_code=200,
        content_type="text/plain",
        body=message,
    )


@app.get("/rasp/ssrf")
@app.post("/rasp/ssrf")
def rasp_ssrf():
    domain = retrieve_arg("domain")

    if not domain:
        return Response(
            status_code=400,
            content_type="text/plain",
            body="missing domain parameter",
        )

    url = f"http://{domain}"

    try:
        with requests.get(url, timeout=1) as response:
            message = f"url {url} open with {len(response.content)} bytes"
    except Exception as exc:
        logger.debug("rasp_ssrf failure", exc_info=True)
        message = f"url {url} could not be open: {exc!r}"

    return Response(
        status_code=200,
        content_type="text/plain",
        body=message,
    )


@app.get("/rasp/sqli")
@app.post("/rasp/sqli")
def rasp_sqli():
    user_id = retrieve_arg("user_id")

    if not user_id:
        return Response(
            status_code=400,
            content_type="text/plain",
            body="missing user_id parameter",
        )

    query = f"SELECT * FROM users WHERE id='{user_id}'"

    try:
        connection = sqlite3.connect(":memory:")
        cursor = connection.execute(query)
        results = list(cursor)
        message = f"DB request with {len(results)} results"
    except Exception as exc:
        logger.debug("rasp_sqli failure for %s", user_id, exc_info=True)
        return Response(
            status_code=201,
            content_type="text/plain",
            body=f"DB request failure: {exc!r}",
        )
    finally:
        try:
            connection.close()
        except Exception:
            pass

    return Response(
        status_code=200,
        content_type="text/plain",
        body=message,
    )


@app.get("/rasp/cmdi")
@app.post("/rasp/cmdi")
def rasp_cmdi():
    command = retrieve_arg("command")

    if isinstance(command, dict):
        command = command.get("cmd")

    if isinstance(command, list) and not command:
        command = None

    if not command:
        return Response(
            status_code=400,
            content_type="text/plain",
            body="missing command parameter",
        )

    try:
        result = subprocess.run(command, capture_output=True)
        message = f"Exec command [{command}] with result: {result}"
        status_code = 200
    except Exception as exc:
        logger.debug("rasp_cmdi failure for %s", command, exc_info=True)
        message = f"Exec command [{command}] failure: {exc!r}"
        status_code = 201

    return Response(
        status_code=status_code,
        content_type="text/plain",
        body=message,
    )


@app.get("/rasp/shi")
@app.post("/rasp/shi")
def rasp_shi():
    list_dir = retrieve_arg("list_dir")

    if list_dir is None:
        return Response(
            status_code=400,
            body="missing list_dir parameter",
            content_type=("text/plain"),
        )
    try:
        command = f"ls {list_dir}"
        res = os.system(command)
        return Response(
            status_code=200,
            body=f"Shell command [{command}] with result: {res}",
            content_type=("text/plain"),
        )
    except Exception as e:
        print(f"Shell command failure: {e!r}", file=sys.stderr)
        return Response(
            status_code=201,
            body=f"Shell command failure: {e!r}",
            content_type=("text/plain"),
        )


@app.get("/external_request")
@app.post("/external_request")
@app.put("/external_request")
@app.route("/external_request", method="TRACE")
def external_request():
    query_params = get_query_params()
    body = app.current_event.decoded_body
    if body:
        content_type = get_header_value("content-type")
        query_params["Content-Type"] = content_type or "application/json"

    status = query_params.pop("status", "200")
    url_extra = query_params.pop("url_extra", "")
    full_url = f"http://internal_server:8089/mirror/{status}{url_extra}"
    method = app.current_event.http_method

    with requests.Session() as session:
        response = session.request(method, full_url, data=body, headers=query_params, timeout=10)
        result = {
            "status": int(response.status_code),
            "headers": dict(response.headers),
            "payload": json.loads(response.text),
        }
        return Response(status_code=200, content_type="application/json", body=result)


@app.get("/users")
def users():
    user = get_query_string_value("user")
    set_user(
        tracer,
        user_id=user,
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return Response(
        status_code=200,
        content_type="text/plain",
        body="Ok",
    )


def lambda_handler(event: dict[str, Any], context: LambdaContext):
    """
    Lambda function handler for AWS Lambda Powertools API Gateway integration.

    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The context object provided by AWS Lambda.

    Returns:
        dict: The response from the API Gateway resolver.
    """
    if event.get("healthcheck"):
        return version_info()
    return app.resolve(event, context)
