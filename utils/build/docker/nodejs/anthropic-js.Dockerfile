FROM datadog/system-tests:anthropic-js.base-v1
ARG FRAMEWORK_VERSION

COPY utils/build/docker/nodejs/anthropic_app /usr/app

RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        npm install @anthropic-ai/sdk; \
    else \
        npm install @anthropic-ai/sdk@$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh
