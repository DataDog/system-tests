FROM node:22-alpine
ARG FRAMEWORK_VERSION

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/openai_app /usr/app
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        bun add --network-concurrency 8 openai; \
    else \
        bun add --network-concurrency 8 openai@$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh
