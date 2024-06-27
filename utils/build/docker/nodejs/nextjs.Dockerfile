FROM node:20-slim

RUN apt-get update && apt-get install -y jq curl

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/nextjs /usr/app

WORKDIR /usr/app

RUN npm install

EXPOSE 7777

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN npm run build
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker startup
ENV DD_DATA_STREAMS_ENABLED=true
ENV PORT=7777
ENV HOSTNAME=0.0.0.0
ENV DD_TRACE_DEBUG=true
RUN echo '#!/bin/bash\nnode .next/standalone/server.js' > app.sh
RUN chmod +x app.sh
ENV NODE_OPTIONS="--require dd-trace/init.js"
CMD ./app.sh
