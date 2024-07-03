FROM ghcr.io/datadog/dd-trace-py/testrunner:9e3bd1fb9e42a4aa143cae661547517c7fbd8924

RUN pyenv global 3.9.16

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD cat SYSTEM_TESTS_LIBRARY_VERSION
