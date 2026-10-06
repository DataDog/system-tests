FROM system_tests_base_python_lambda_python_lambda_runtime

COPY utils/build/docker/python_lambda/install_datadog_lambda.sh binaries* /binaries/
RUN /binaries/install_datadog_lambda.sh

# Setup the aws_lambda handler
COPY utils/build/docker/python_lambda/function/. ${LAMBDA_TASK_ROOT}
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

ENV DD_LAMBDA_HANDLER=handler.lambda_handler
ENV SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE=apigateway-rest

LABEL system-tests.lambda-proxy.event-type=apigateway-rest

ENTRYPOINT ["/bin/sh"]
