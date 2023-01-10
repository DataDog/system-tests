
FROM eclipse-temurin:8 as agent

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh


FROM ghcr.io/datadog/system-tests/java11_mvn_build:latest as build

WORKDIR /app

# Copy application sources
COPY ./utils/build/docker/java/spring-boot/pom.xml .
COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mv ./src/main/resources/application-native.properties ./src/main/resources/application.properties

# Copy tracer
COPY --from=agent /dd-tracer/dd-java-agent.jar .

# Build native application
RUN mvn package -P spring-native

FROM ubuntu

WORKDIR /app
COPY --from=agent /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject .


ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

RUN echo "#!/bin/bash\n/app/myproject" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
