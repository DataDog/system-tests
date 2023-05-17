
FROM ghcr.io/datadog/dd-trace-py/testrunner:7ce49bd78b0d510766fc5db12756a8840724febc
WORKDIR /client
RUN pyenv global 3.9.11
RUN python3.9 -m pip install fastapi==0.89.1 uvicorn==0.20.0
RUN python3.9 -m pip install ddtrace
