FROM maven:3.9-eclipse-temurin-11 as build

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Dmaven.repo.local=/maven package

COPY ./utils/build/docker/java_otel/install_opentelemetry.sh binaries* /binaries/
RUN /binaries/install_opentelemetry.sh

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /app/app.jar
COPY --from=build /otel-tracer/opentelemetry-javaagent.jar .

COPY ./utils/build/docker/java_otel/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV APP_EXTRA_ARGS="--server.port=7777"
CMD [ "/app/app.sh" ]
