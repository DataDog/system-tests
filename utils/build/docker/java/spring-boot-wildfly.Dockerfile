FROM eclipse-temurin:8 as agent

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM ghcr.io/datadog/system-tests/java11_mvn_build:latest as build

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Pwildfly package


FROM adoptopenjdk:11-jre-hotspot

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT-bootable.jar .
COPY --from=agent /dd-tracer/dd-java-agent.jar .

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

RUN echo "#!/bin/bash\njava -Xmx362m  -javaagent:/app/dd-java-agent.jar -jar /app/myproject-0.0.1-SNAPSHOT-bootable.jar  -Djboss.http.port=7777 -b=0.0.0.0" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
