import os
import sys
from samcli.local.apigw.event_constructor import construct_v1_event
from samcli.local.apigw.local_apigw_service import LocalApigwService

# Create super simple catch-all flask app
from flask import Flask, request
from requests import post

PORT = 7777

RIE_HOST = os.environ.get("RIE_HOST", "lambda-weblog")
RIE_PORT = os.environ.get("RIE_PORT", "8080")
FUNCTION_NAME = os.environ.get("FUNCTION_NAME", "function")
RIE_URL = f"http://{RIE_HOST}:{RIE_PORT}/2015-03-31/functions/{FUNCTION_NAME}/invocations"

app = Flask(__name__)


@app.route("/")
@app.route("/<path:path>")
def main(path=""):
    converted_event = construct_v1_event(request, PORT, binary_types=[], stage_name="Prod")

    response = post(
        RIE_URL,
        json=converted_event,
        headers={"Content-Type": "application/json"},
    )

    (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
        response.content.decode("utf-8"), binary_types=[], flask_request=request, event_type="Api"
    )

    return app.response_class(response=body, status=status_code, headers=headers)
