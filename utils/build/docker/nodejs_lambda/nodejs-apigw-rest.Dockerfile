FROM public.ecr.aws/lambda/nodejs:18

RUN yum install -y unzip findutils socat && yum clean all

# Add the Datadog Extension
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:latest /opt/. /opt/

COPY utils/build/docker/nodejs_lambda/install_datadog_lambda.sh binaries* /binaries/
RUN chmod +x /binaries/install_datadog_lambda.sh && /binaries/install_datadog_lambda.sh

# Setup the Lambda handler
COPY utils/build/docker/nodejs_lambda/function/. ${LAMBDA_TASK_ROOT}
RUN cd ${LAMBDA_TASK_ROOT} && (npm ci || (sleep 30 && npm ci))

ENV DD_LAMBDA_HANDLER=handler.handler
ENV _HANDLER=/opt/nodejs/node_modules/datadog-lambda-js/handler.handler
ENV SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE=apigateway-rest

LABEL system-tests.lambda-proxy.event-type=apigateway-rest

COPY utils/build/docker/nodejs_lambda/app.sh ${LAMBDA_TASK_ROOT}/app.sh
RUN chmod +x ${LAMBDA_TASK_ROOT}/app.sh

ENTRYPOINT ["/var/task/app.sh"]
