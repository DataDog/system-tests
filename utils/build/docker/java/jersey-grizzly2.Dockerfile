FROM maven:3.9-eclipse-temurin-11 as build

WORKDIR /app

ENV MAVEN_OPTS="-Daether.dependencyCollector.impl=bf -Dmaven.artifact.threads=4"

COPY ./utils/build/docker/java/jersey-grizzly2/pom.xml .
# Dependencies are downloaded first to cache them as long as pom.xml does not change.
# Use mvn package while ignoring errors, rather than go-offline to fetch less dependencies.
RUN mvn package -DskipTests || true

COPY ./utils/build/docker/java/jersey-grizzly2/src ./src
RUN mvn package -DskipTests

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/jersey-grizzly2-1.0-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_INTEGRATION_GRIZZLY_ENABLED=true

CMD [ "/app/app.sh" ]
