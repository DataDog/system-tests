# The base image holds a maven repository filled from play/pom.xml: maven runs offline here
FROM system_tests_base_java_play AS build

COPY ./utils/build/docker/java/play/pom.xml .
COPY ./utils/build/docker/java/play/app ./app
COPY ./utils/build/docker/java/play/conf ./conf
COPY ./utils/build/docker/java/iast-common/src /iast-common/src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh "-o -Dmaven.repo.local=/maven"
RUN mvn -o -Dmaven.repo.local=/maven -B play2:routes-compile package play2:dist-exploded

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/target/dist/play-app-1.0.0 .
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY ./utils/build/docker/java/app-play.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

CMD [ "/app/app.sh" ]
