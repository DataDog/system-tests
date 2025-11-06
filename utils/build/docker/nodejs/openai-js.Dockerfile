FROM node:22-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/openai /usr/app

WORKDIR /usr/app

RUN npm install || sleep 60 && npm install
RUN npm install openai@$FRAMEWORK_VERSION

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
ENV DD_TRACE_EXPRESS_ENABLED=false
ENV DD_TRACE_HTTP_ENABLED=false
ENV DD_TRACE_DNS_ENABLED=false
ENV DD_TRACE_NET_ENABLED=false
ENV DD_TRACE_FETCH_ENABLED=false
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node app.js' >> app.sh
ENV NODE_OPTIONS="--import dd-trace/initialize.mjs"
CMD ./app.sh