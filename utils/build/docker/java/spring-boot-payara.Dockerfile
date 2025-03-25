FROM maven:3.9-eclipse-temurin-11 as build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -Ppayara -B dependency:go-offline
RUN mvn dependency:get -Dartifact=org.codehaus.woodstox:stax2-api:4.2.1

COPY ./utils/build/docker/java/spring-boot/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh -Dmaven.repo.local=/maven
RUN mvn -Dmaven.repo.local=/maven -Ppayara package

ARG PAYARA_VERSION=5.2022.1
RUN curl https://nexus.payara.fish/repository/payara-community/fish/payara/extras/payara-micro/${PAYARA_VERSION}/payara-micro-${PAYARA_VERSION}.jar -o /binaries/payara-micro.jar

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.war /app/app.war
COPY --from=build /dd-tracer/dd-java-agent.jar .
COPY --from=build /binaries/payara-micro.jar /app/payara-micro.jar
COPY --from=build /root/.m2/repository/org/codehaus/woodstox/stax2-api/4.2.1/stax2-api-4.2.1.jar /app/stax2-api-4.2.1.jar

COPY ./utils/build/docker/java/app-payara.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true
ENV APP_EXTRA_ARGS="--port 7777"
# https://docs.hazelcast.com/hazelcast/5.3/phone-homes
ENV HZ_PHONE_HOME_ENABLED=false
# https://blog.payara.fish/faster-payara-micro-startup-times-with-openj9
ENV payaramicro_noCluster=true

CMD [ "/app/app.sh" ]
