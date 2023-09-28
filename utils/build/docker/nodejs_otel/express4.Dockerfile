FROM node:16

RUN apt-get update && apt-get install -y jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4 /usr/app

WORKDIR /usr/app

RUN npm install

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

RUN npm install --save @opentelemetry/api
RUN npm install --save @opentelemetry/auto-instrumentations-node

# docker startup
RUN echo '#!/bin/bash\nnode --require @opentelemetry/auto-instrumentations-node/register app.js' > app.sh
RUN chmod +x app.sh
CMD ./app.sh