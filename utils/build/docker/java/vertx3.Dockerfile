FROM maven:3.9-eclipse-temurin-11 as build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/vertx3/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/vertx3/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh -Dmaven.repo.local=/maven
RUN mvn -Dmaven.repo.local=/maven package

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/vertx3-1.0-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
# FIXME: Fails on DEFAULT scenario, see APPSEC-51406
# ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true
ENV DD_IAST_VULNERABILITIES_PER_REQUEST=10

CMD [ "/app/app.sh" ]
