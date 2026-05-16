FROM ghcr.io/datadog/system-tests:openai-js.base-v6903
ARG FRAMEWORK_VERSION

COPY utils/build/docker/nodejs/openai_app /usr/app

RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        npm install openai; \
    else \
        npm install openai@$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh
