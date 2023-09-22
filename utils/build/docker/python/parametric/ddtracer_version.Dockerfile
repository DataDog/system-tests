
FROM python:3.9-slim

ARG BUILD_MODULE=''
ENV PYTHON_DDTRACE_PACKAGE=$BUILD_MODULE

WORKDIR /client

# install bin dependancies
RUN apt-get update && apt-get install -y git gcc g++ make cmake

RUN if [ -z "${PYTHON_DDTRACE_PACKAGE}" ]; then pip install ddtrace; else pip install "$PYTHON_DDTRACE_PACKAGE"; fi
CMD python -c "import ddtrace; print(ddtrace.__version__)"