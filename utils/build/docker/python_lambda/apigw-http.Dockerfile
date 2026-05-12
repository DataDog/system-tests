FROM public.ecr.aws/lambda/python:3.13

RUN dnf install -y unzip findutils socat

# Add the Datadog Extension
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:latest /opt/. /opt/

COPY utils/build/docker/python_lambda/install_datadog_lambda.sh binaries* /binaries/
RUN /binaries/install_datadog_lambda.sh

# Setup the aws_lambda handler
COPY utils/build/docker/python_lambda/function/. ${LAMBDA_TASK_ROOT}
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

ENV DD_LAMBDA_HANDLER=handler.lambda_handler
ENV SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE=apigateway-http

LABEL system-tests.lambda-proxy.event-type=apigateway-http

ENTRYPOINT ["/bin/sh"]
