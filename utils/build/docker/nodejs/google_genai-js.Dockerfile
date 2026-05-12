FROM datadog/system-tests:google_genai-js.base-v1
ARG FRAMEWORK_VERSION

COPY utils/build/docker/nodejs/google_genai_app /usr/app

RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        npm install @google/genai; \
    else \
        npm install @google/genai@$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh
