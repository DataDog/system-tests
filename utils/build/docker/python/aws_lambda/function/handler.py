from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing.lambda_context import LambdaContext
from aws_lambda_powertools.event_handler import Response

import ddtrace  # type: ignore[import-untyped]

app = APIGatewayRestResolver()


@app.get("/hello")
def hello():
    return {"message": "Hello, World!", "headers": {"X-Custom": "having fun"}}


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
    response = app.resolve(event, context)
    return response
