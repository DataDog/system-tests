from typing import Any
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing.lambda_context import LambdaContext
from aws_lambda_powertools.event_handler import Response

import logging
import os

import ddtrace

logger = logging.getLogger(__name__)


app = APIGatewayRestResolver()


def version_info():
    return {
        "status": "ok",
        "library": {
            "name": "ddtrace",
            "version": ddtrace.__version__,
        },
        "extension": {
            "name": "datadog-lambda-extension",
            "version": os.environ.get("EXTENSION_VERSION", "unknown"),
        },
    }


@app.get("/healthcheck")
def healthcheck_route():
    return Response(
        status_code=200,
        content_type="application/json",
        body=version_info(),
    )


@app.get("/")
@app.post("/")
def root():
    return Response(status_code=200, content_type="text/plain", body="Hello, World!\n")


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
