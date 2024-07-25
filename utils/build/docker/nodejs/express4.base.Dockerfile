FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

WORKDIR /usr/app

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true
ENV DD_TRACE_HEADER_TAGS=user-agent

CMD ./app.sh
