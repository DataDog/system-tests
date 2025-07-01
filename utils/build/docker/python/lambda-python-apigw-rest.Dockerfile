ARG PYTHON_VERSION=3.13

FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}

RUN dnf install -y unzip

# Add the Datadog Extension
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:latest /opt/. /opt/

# Add the Datadog Lambda Python Layer
COPY binaries/*.zip /binaries/
RUN unzip /binaries/*.zip -d /opt

# Setup the aws_lambda handler
COPY utils/build/docker/python/aws_lambda/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY utils/build/docker/python/aws_lambda/function/handler.py ${LAMBDA_TASK_ROOT}

ENV DD_LAMBDA_HANDLER=handler.lambda_handler

CMD ["datadog_lambda.handler.handler"]
