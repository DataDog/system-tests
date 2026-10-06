FROM system_tests_base_python_openai_py
ARG FRAMEWORK_VERSION

WORKDIR /app

RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        python -m pip install --retries 10 --timeout 120 openai; \
    else \
        python -m pip install --retries 10 --timeout 120 openai==$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/python/openai_app/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh
RUN mkdir /integration-framework-tracer-logs

CMD ["ddtrace-run", "python", "-m", "integration_frameworks", "openai"]
