FROM node:18-alpine AS build

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4 /usr/app

WORKDIR /usr/app

ENV NODE_ENV=production

RUN npm install

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# ==============================================================================

FROM node:18-alpine

COPY --from=build /usr/app /usr/app

WORKDIR /usr/app

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker startup
RUN printf '#!/bin/bash\nnode app.js' > app.sh
RUN chmod +x app.sh
CMD ./app.sh

# docker build -f utils/build/docker/nodejs.datadog.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
