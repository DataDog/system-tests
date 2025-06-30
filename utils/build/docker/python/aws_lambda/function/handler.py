from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing.lambda_context import LambdaContext
from aws_lambda_powertools.event_handler import Response

import logging
import os

import ddtrace

logger = logging.getLogger(__name__)


app = APIGatewayRestResolver()


@app.get("/healthcheck")
def healthcheck():
    return Response(
        status_code=200,
        content_type="application/json",
        body={
            "status": "ok",
            "library": {
                "name": "ddtrace",
                "version": ddtrace.__version__,
            },
            "extension": {
                "name": "datadog-lambda-extension",
                "version": os.environ.get("EXTENSION_VERSION", "unknown"),
            },
        },
    )


def lambda_handler(event, context: LambdaContext):
    """
    Lambda function handler for AWS Lambda Powertools API Gateway integration.

    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The context object provided by AWS Lambda.

    Returns:
        dict: The response from the API Gateway resolver.
    """
    return app.resolve(event, context)
