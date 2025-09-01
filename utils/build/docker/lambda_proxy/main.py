import logging
import os

from flask import Flask, request
from requests import post

from samcli.local.apigw.event_constructor import construct_v1_event, construct_v2_event_http
from samcli.local.apigw.local_apigw_service import LocalApigwService
from samcli.local.apigw.local_apigw_service import PathConverter

logger = logging.getLogger()

PORT = 7777
BINARY_TYPES = ["application/octet-stream"]

RIE_HOST = os.environ.get("RIE_HOST", "lambda-weblog")
RIE_PORT = os.environ.get("RIE_PORT", "8080")
FUNCTION_NAME = os.environ.get("FUNCTION_NAME", "function")
RIE_URL = f"http://{RIE_HOST}:{RIE_PORT}/2015-03-31/functions/{FUNCTION_NAME}/invocations"

LAMBDA_EVENT_TYPE: str | None = os.environ.get("LAMBDA_EVENT_TYPE")

app = Flask(__name__)

app.config["PROVIDE_AUTOMATIC_OPTIONS"] = False


def invoke_lambda_function_api_gateway_rest():
    """
    This function is used to invoke the Lambda function with the provided event.
    It constructs a v1 event from the Flask request and sends it to the RIE URL.
    """
    converted_event = construct_v1_event(
        request,
        PORT,
        binary_types=BINARY_TYPES,
        stage_name="Prod",
    )

    response = post(
        RIE_URL,
        json=converted_event,
        headers={"Content-Type": "application/json"},
    )

    (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
        response.content.decode("utf-8"),
        binary_types=BINARY_TYPES,
        flask_request=request,
        event_type="Api",
    )

    return app.response_class(response=body, status=status_code, headers=headers)


def invoke_lambda_function_api_gateway_http():
    """
    This function is used to invoke the Lambda function with the provided event.
    It constructs a v2 event http from the Flask request and sends it to the RIE URL.
    """

    path = PathConverter.convert_path_to_api_gateway(request.path)
    route_key = LocalApigwService._v2_route_key(request.method, path, is_default_route=False)
    converted_event = construct_v2_event_http(request, PORT, binary_types=BINARY_TYPES, route_key=route_key)

    response = post(
        RIE_URL,
        json=converted_event,
        headers={"Content-Type": "application/json"},
    )

    (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
        response.content.decode("utf-8"), binary_types=BINARY_TYPES, flask_request=request
    )

    return app.response_class(response=body, status=status_code, headers=headers)


match LAMBDA_EVENT_TYPE:
    case "apigateway-rest":
        lambda_invoker = invoke_lambda_function_api_gateway_rest
    case "apigateway-http":
        lambda_invoker = invoke_lambda_function_api_gateway_http
    case _:
        logger.error(
            f"Unsupported Lambda event type: {LAMBDA_EVENT_TYPE}",
        )
        exit(1)

ROUTES = [
    ("/", ["GET", "POST", "OPTIONS"]),
    ("/finger_print", ["GET"]),
    ("/headers", ["GET"]),
    ("/healthcheck", ["GET"]),
    ("/params/<path>/", ["GET", "POST", "OPTIONS"]),
    ("/session/new", ["GET"]),
    ("/tag_value/<tag_value>/<status_code>", ["GET", "POST", "OPTIONS"]),
    ("/user_login_success_event", ["GET"]),
    ("/users", ["GET"]),
    ("/waf", ["GET", "POST", "OPTIONS"]),
    ("/waf/", ["GET", "POST", "OPTIONS"]),
    ("/waf/<path>", ["GET", "POST", "OPTIONS"]),
    ("/.git", ["GET"]),
]

for endpoint, methods in ROUTES:
    app.add_url_rule(
        endpoint,
        endpoint,
        lambda **kwargs: lambda_invoker(),
        methods=methods,
    )
