
FROM ghcr.io/datadog/dd-trace-py/testrunner:7ce49bd78b0d510766fc5db12756a8840724febc
WORKDIR /app
RUN pyenv global 3.9.11
RUN python3.9 -m pip install fastapi==0.89.1 uvicorn==0.20.0
COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_PATCH_MODULES="fastapi:false"
