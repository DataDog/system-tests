FROM node:22-alpine
ARG FRAMEWORK_VERSION

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/openai_app /usr/app
RUN npm ci || (sleep 30 && npm ci)

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