FROM maven:3.9-eclipse-temurin-21 AS build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot-virtual-threads/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/spring-boot-virtual-threads/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh -Dmaven.repo.local=/maven
RUN mvn -Dmaven.repo.local=/maven package

FROM eclipse-temurin:21-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true
ENV APP_EXTRA_ARGS="--server.port=7777"
# One carrier: a pinned or exhausted ForkJoin worker stalls every virtual thread.
ENV JAVA_OPTS="-Djdk.virtualThreadScheduler.parallelism=1 -Djdk.virtualThreadScheduler.maxPoolSize=1 -Djdk.tracePinnedThreads=full"

CMD [ "/app/app.sh" ]
