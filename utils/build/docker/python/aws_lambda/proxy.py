import os
import subprocess
import sys
from samcli.local.apigw.event_constructor import construct_v1_event
from samcli.local.apigw.local_apigw_service import LocalApigwService

# Create super simple catch-all flask app
from flask import Flask, request
from requests import post

PORT = 7777
RIE_URL = f"http://localhost:8080/2015-03-31/functions/function/invocations"

app = Flask(__name__)


@app.route("/")
@app.route("/<path:path>")
def catch_all(path):
    converted_event = construct_v1_event(request, PORT, binary_types=[])
    # Send POST request to RIE running on local server
    response = post(
        RIE_URL,
        json=converted_event,
        headers={"Content-Type": "application/json"},
    )

    (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
        response.content.decode("utf-8"), binary_types=[], flask_request=request, event_type="Api"
    )

    return app.response_class(response=body, status=status_code, headers=headers)


if __name__ == "__main__":
    env = os.environ.copy()
    env["_HANDLER"] = "handler.lambda_handler"

    subprocess.Popen(
        [
            "/usr/local/bin/aws-lambda-rie",
            "/var/runtime/bootstrap",
        ],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    app.run(host="0.0.0.0", port=PORT)
