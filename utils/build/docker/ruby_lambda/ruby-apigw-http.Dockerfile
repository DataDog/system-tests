FROM public.ecr.aws/lambda/ruby:3.4

RUN dnf install -y unzip findutils socat gcc make redhat-rpm-config

RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:latest /opt/. /opt/

COPY utils/build/docker/ruby_lambda/install_datadog_lambda.sh binaries* /binaries/
RUN /binaries/install_datadog_lambda.sh

COPY utils/build/docker/ruby_lambda/function/handler.rb utils/build/docker/ruby_lambda/function/app.sh ${LAMBDA_TASK_ROOT}

ENV SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE=apigateway-http
LABEL system-tests.lambda-proxy.event-type=apigateway-http
ENTRYPOINT ["/bin/sh"]
