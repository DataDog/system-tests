FROM maven:3.8-jdk-8 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

ENV MAVEN_REPO=/maven
ENV MAVEN_OPTS=-Dmaven.repo.local=/maven
COPY ./utils/build/docker/java/install_dependencies.sh .
COPY ./utils/build/docker/java/spring-boot/spring-boot.dep.lock .
COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN ./install_dependencies.sh spring-boot.dep.lock

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn package -DskipTests

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar .
COPY --from=build /dd-tracer/dd-java-agent.jar .

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh
ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
ENV UDS_WEBLOG=1
COPY utils/build/docker/java/spring-boot/app.sh app.sh
