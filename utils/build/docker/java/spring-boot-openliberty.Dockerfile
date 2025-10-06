FROM maven:3.9-eclipse-temurin-11 as build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .

COPY ./utils/build/docker/java/spring-boot/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mvn -Popenliberty package

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .
COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
# FIXME: Fails on APPSEC_BLOCKING, see APPSEC-51405
# ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

COPY ./utils/build/docker/java/ConfigChaining.properties app/ConfigChaining.properties
ENV JVM_ARGS='-javaagent:/app/dd-java-agent.jar'

RUN echo "#!/bin/bash\njava -Xmx362m -jar /app/app.jar" > app.sh
RUN chmod +x app.sh
CMD [ "/app/app.sh" ]
