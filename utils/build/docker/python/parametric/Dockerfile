
FROM ghcr.io/datadog/dd-trace-py/testrunner:9e3bd1fb9e42a4aa143cae661547517c7fbd8924
WORKDIR /app
RUN pyenv global 3.9.16
RUN python3.9 -m pip install fastapi==0.89.1 uvicorn==0.20.0
COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_PATCH_MODULES="fastapi:false"
