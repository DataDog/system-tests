import logging
import urllib
import urllib.parse

from typing import Any

from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing.lambda_context import LambdaContext
from aws_lambda_powertools.event_handler import Response

import datadog_lambda
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace.contrib.trace_utils import set_user
from ddtrace.trace import tracer


logger = logging.getLogger(__name__)


app = APIGatewayRestResolver()

_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


def version_info():
    return {
        "status": "ok",
        "library": {
            "name": "python_lambda",
            "version": datadog_lambda.__version__,
        },
    }


@app.get("/tag_value/<tag_value>/<status_code>")
@app.route("/tag_value/<tag_value>/<status_code>", method="OPTIONS")
def tag_value(tag_value: str, status_code: int):
    appsec_trace_utils.track_custom_event(
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    return Response(
        status_code=status_code,
        content_type="text/plain",
        body="Value tagged",
        headers=app.current_event.query_string_parameters,
    )


@app.get("/")
@app.post("/")
@app.route("/", method="OPTIONS")
def root():
    return Response(status_code=200, content_type="text/plain", body="Hello, World!\n")


@app.get("/headers")
def headers():
    return Response(status_code=200, body="OK", headers={"Content-Language": "en-US", "Content-Type": "text/plain"})


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
@app.get("/waf/")
@app.post("/waf/")
@app.get("/waf/<path>")
@app.post("/waf/<path>")
@app.route("/waf/<path>", method="OPTIONS")
def waf_params(path: str):
    return Response(
        status_code=200,
        content_type="text/plain",
        body="Hello, World!\n",
    )


@app.post("/tag_value/<tag_value>/<status_code>")
def tag_value_post(tag_value: str, status_code: int):
    appsec_trace_utils.track_custom_event(
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    if tag_value.startswith("payload_in_response_body"):
        # Get form data from the current event
        body = app.current_event.body or ""
        if app.current_event.is_base64_encoded:
            import base64

            body = base64.b64decode(body).decode("utf-8")

        form_data = urllib.parse.parse_qs(body)

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


@app.get("/users")
def users():
    user = app.current_event.query_string_parameters.get("user")
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
