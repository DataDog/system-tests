FROM maven:3.9-eclipse-temurin-11 as build

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline -Ppayara

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Dmaven.repo.local=/maven package -Ppayara

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM payara/server-full:latest

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.war /opt/payara/deployments/app.war
COPY --from=build /dd-tracer/dd-java-agent.jar .
COPY ./utils/build/docker/java/app-payara.sh /app/app.sh

USER root

# DEBUG
#RUN sed -i -e 's~INFO~FINE~g' /opt/payara/appserver/glassfish/domains/domain1/config/logging.properties

RUN set -eux;\
    mkdir -p /app;\
    chown -R payara /app;\
    chmod a+rwx / /app
USER payara

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_DATA_STREAMS_ENABLED=true

# payara/micro uses an entry point and we need to unset it.
# ENTRYPOINT []
# but payara/server-full uses tini, which is fine.
CMD ["/app/app.sh"]
