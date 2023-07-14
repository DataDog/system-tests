FROM maven:3.9-eclipse-temurin-11 as build

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/integrations-db-sql/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/integrations-db-sql/src ./src
RUN mvn -Dmaven.repo.local=/maven package

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target /app/target
COPY --from=build /app/src /app/src
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/app-integrations-db-sql.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV APP_PORT="7777"
ENV DD_DATA_STREAMS_ENABLED=true

CMD [ "/app/app.sh" ]
