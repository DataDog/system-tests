import os

from flask import Flask, request
from requests import post

from samcli.local.apigw.event_constructor import construct_v1_event
from samcli.local.apigw.local_apigw_service import LocalApigwService

PORT = 7777

RIE_HOST = os.environ.get("RIE_HOST", "lambda-weblog")
RIE_PORT = os.environ.get("RIE_PORT", "8080")
FUNCTION_NAME = os.environ.get("FUNCTION_NAME", "function")
RIE_URL = f"http://{RIE_HOST}:{RIE_PORT}/2015-03-31/functions/{FUNCTION_NAME}/invocations"

app = Flask(__name__)

app.config["PROVIDE_AUTOMATIC_OPTIONS"] = False


def invoke_lambda_function():
    """
    This function is used to invoke the Lambda function with the provided event.
    It constructs a v1 event from the Flask request and sends it to the RIE URL.
    """
    converted_event = construct_v1_event(request, PORT, binary_types=["application/octet-stream"], stage_name="Prod")

    response = post(
        RIE_URL,
        json=converted_event,
        headers={"Content-Type": "application/json"},
    )

    (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
        response.content.decode("utf-8"), binary_types=[], flask_request=request, event_type="Api"
    )

    return app.response_class(response=body, status=status_code, headers=headers)


@app.route("/", methods=["GET", "POST", "OPTIONS"])
@app.route("/finger_print")
@app.get("/headers")
@app.get("/healthcheck")
@app.route("/params/<path>/", methods=["GET", "POST", "OPTIONS"])
@app.route("/tag_value/<string:tag_value>/<int:status_code>", methods=["GET", "POST", "OPTIONS"])
@app.get("/users")
@app.route("/waf", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/<path:url>", methods=["GET", "POST", "OPTIONS"])
@app.get("/.git")
def main(**kwargs):
    return invoke_lambda_function()
