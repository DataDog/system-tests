# The base image holds a maven repository filled from spring-boot/pom.xml (tomcat profile): maven runs offline here
FROM system_tests_base_java_spring_boot AS build

COPY ./utils/build/docker/java/iast-common/src /iast-common/src
COPY ./utils/build/docker/java/spring-boot/pom.xml .
COPY ./utils/build/docker/java/spring-boot/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh "-o -Dmaven.repo.local=/maven"
RUN mvn -o -Dmaven.repo.local=/maven -B package

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar .
COPY --from=build /dd-tracer/dd-java-agent.jar .

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh
ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
RUN apt-get update && apt-get install socat -y
ENV UDS_WEBLOG=1
COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY utils/build/docker/java/spring-boot/app.sh app.sh
