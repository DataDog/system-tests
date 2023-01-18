ARG TRACER_IMAGE=agent_local

#TODO RMM: The images will be in dd-trace-java repository. Now for tests purposes we are using system-tests repository
FROM ghcr.io/datadog/system-tests/dd-java-agent:LATEST_SNAPSHOT as agent_latest_snapshot

FROM ghcr.io/datadog/system-tests/dd-java-agent:LATEST as agent_latest

FROM ghcr.io/datadog/system-tests/dd-java-agent:LATEST_SNAPSHOT as agent_local

COPY ./binaries/dd-java-agent.jar /dd-tracer/
RUN sh library_version.sh 

FROM $TRACER_IMAGE as agent


FROM ghcr.io/graalvm/graalvm-ce:ol8-java11-22 as build

ARG TRACER_LIBRARY_ORIGIN=agent

RUN gu install native-image && native-image

# Install maven
RUN curl https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz --output /opt/maven.tar.gz && \
	tar xzvf /opt/maven.tar.gz --directory /opt && \
	rm /opt/maven.tar.gz

WORKDIR /app

# Copy application sources
COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && /opt/apache-maven-3.8.6/bin/mvn -Dmaven.repo.local=/maven -B dependency:resolve-plugins dependency:go-offline -P spring-native
#Force to download all pom from deps
RUN /opt/apache-maven-3.8.6/bin/mvn -Dmaven.repo.local=/maven verify --fail-never

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mv ./src/main/resources/application-native.properties ./src/main/resources/application.properties

# Copy tracer
COPY --from=agent /dd-tracer/dd-java-agent.jar .

# Build native application
RUN /opt/apache-maven-3.8.6/bin/mvn -Dmaven.repo.local=/maven package -P spring-native

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
