ARG EXTENSION_VERSION=82
ARG PYTHON_VERSION=3.13
FROM public.ecr.aws/datadog/lambda-extension:${EXTENSION_VERSION} AS datadog-extension

FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}
ARG EXTENSION_VERSION
ENV EXTENSION_VERSION=${EXTENSION_VERSION}

# Install the unzip utility
RUN dnf install -y unzip

# Add the Datadog Extension
RUN mkdir -p /opt/extensions
COPY --from=datadog-extension /opt/. /opt/

# Add the Datadog Lambda Python Layer
COPY binaries/*.zip /binaries/
RUN unzip /binaries/*.zip -d /opt

# Setup the aws_lambda handler
COPY utils/build/docker/python/aws_lambda/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY utils/build/docker/python/aws_lambda/function/handler.py ${LAMBDA_TASK_ROOT}

ENV DD_LAMBDA_HANDLER=handler.lambda_handler

CMD ["datadog_lambda.handler.handler"]
