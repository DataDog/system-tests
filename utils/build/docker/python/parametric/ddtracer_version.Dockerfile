FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y git gcc g++ make cmake curl

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD cat SYSTEM_TESTS_LIBRARY_VERSION
