FROM maven:3.9-eclipse-temurin-11 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

ENV MAVEN_REPO=/maven
ENV MAVEN_OPTS=-Dmaven.repo.local=/maven
COPY ./utils/build/docker/java/install_dependencies.sh .
COPY ./utils/build/docker/java/spring-boot/spring-boot-undertow.dep.lock .
COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN ./install_dependencies.sh spring-boot-undertow.dep.lock -Pundertow

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Pundertow package -DskipTests

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV APP_EXTRA_ARGS="--server.port=7777"

CMD [ "/app/app.sh" ]
