FROM maven:3.9-eclipse-temurin-11 as build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/spring-boot/src ./src
COPY ./utils/build/docker/java/install_*.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh -Dmaven.repo.local=/maven
RUN mvn -Dmaven.repo.local=/maven package

RUN /binaries/install_drop_in.sh

FROM eclipse-temurin:11-jre

WORKDIR /app

# Agentless intake tests send HTTPS through the system-tests mitmproxy. Trust the
# checked-in test CA so Java validates that intercepted TLS connection.
COPY ./utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer /tmp/system-tests-mitmproxy-ca.cer
RUN keytool -importcert -noprompt -cacerts -storepass changeit \
    -alias system-tests-mitmproxy \
    -file /tmp/system-tests-mitmproxy-ca.cer \
    && rm /tmp/system-tests-mitmproxy-ca.cer

COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/opentelemetry-javaagent-r2dbc.jar .
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true
ENV APP_EXTRA_ARGS="--server.port=7777"
ENV DD_DATA_STREAMS_ENABLED=true

CMD [ "/app/app.sh" ]
