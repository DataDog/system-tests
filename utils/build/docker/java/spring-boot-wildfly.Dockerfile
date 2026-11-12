# The base image holds a maven repository filled from spring-boot/pom.xml (wildfly profile): maven runs offline here
FROM system_tests_base_java_spring_boot_wildfly AS build

COPY ./utils/build/docker/java/iast-common/src /iast-common/src
COPY ./utils/build/docker/java/spring-boot/pom.xml .
COPY ./utils/build/docker/java/spring-boot/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh "-o -Dmaven.repo.local=/maven"
RUN mvn -o -Dmaven.repo.local=/maven -B -Pwildfly package

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT-bootable.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_APP_CUSTOMLOGMANAGER=true
ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true
ENV APP_EXTRA_ARGS="-Djboss.http.port=7777 -b=0.0.0.0"

CMD [ "/app/app.sh" ]
