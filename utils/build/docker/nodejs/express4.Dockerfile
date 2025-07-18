FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express /usr/app

WORKDIR /usr/app

ENV NODE_ENV=production

RUN npm install || npm install
RUN npm install "express@4.17.2" "apollo-server-express@3.13.0" "express-mongo-sanitize@2.2.0" \
  || npm install "express@4.17.2" "apollo-server-express@3.13.0" "express-mongo-sanitize@2.2.0"

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN chmod +x app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker build -f utils/build/docker/nodejs/express4.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
