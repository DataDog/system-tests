FROM node:20-alpine

RUN apk add --no-cache bash curl git jq

WORKDIR /usr/app

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/nodejs/app.sh /usr/app

RUN chmod +x install_ddtrace.sh
RUN chmod +x app.sh

EXPOSE 7777

ENV DD_DATA_STREAMS_ENABLED=true
ENV DD_TRACE_HEADER_TAGS=user-agent
ENV DD_TRACE_DEBUG=true

ENV PORT=7777
ENV HOSTNAME=0.0.0.0

CMD ./app.sh
