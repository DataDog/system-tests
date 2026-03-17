FROM node:22-alpine
ARG FRAMEWORK_VERSION

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/anthropic_app /usr/app

WORKDIR /usr/app

RUN npm install || sleep 60 && npm install
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