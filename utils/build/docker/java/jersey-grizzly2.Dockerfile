# The base image holds a maven repository filled from jersey-grizzly2/pom.xml: maven runs offline here
FROM system_tests_base_java_jersey_grizzly2 AS build

COPY ./utils/build/docker/java/iast-common/src /iast-common/src
COPY ./utils/build/docker/java/jersey-grizzly2/pom.xml .
COPY ./utils/build/docker/java/jersey-grizzly2/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh "-o -Dmaven.repo.local=/maven"
RUN mvn -o -Dmaven.repo.local=/maven -B package

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/target/jersey-grizzly2-1.0-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true
ENV DD_INTEGRATION_GRIZZLY_ENABLED=true

CMD [ "/app/app.sh" ]
