
FROM eclipse-temurin:8 as agent

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh


FROM ghcr.io/graalvm/graalvm-ce:ol8-java11-22 as build

RUN gu install native-image && native-image

# Install maven
RUN curl https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz --output /opt/maven.tar.gz && \
	tar xzvf /opt/maven.tar.gz --directory /opt && \
	rm /opt/maven.tar.gz

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

# Copy application sources
COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && /opt/apache-maven-3.8.6/bin/mvn -Dmaven.repo.local=/maven -B dependency:resolve-plugins dependency:go-offline -Pspring-native
#Force to download all pom from deps
RUN /opt/apache-maven-3.8.6/bin/mvn -Dmaven.repo.local=/maven verify --fail-never -Pspring-native

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mv ./src/main/resources/application-native.properties ./src/main/resources/application.properties

# Copy tracer
COPY --from=agent /dd-tracer/dd-java-agent.jar .

# Build native application
RUN /opt/apache-maven-3.8.6/bin/mvn -Dmaven.repo.local=/maven package -Pspring-native

FROM ubuntu

RUN apt-get update && apt-get install -y curl

WORKDIR /app
COPY --from=agent /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject .


ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

RUN echo "#!/bin/bash\nexec /app/myproject" > app.sh
RUN chmod +x app.sh
CMD [ "/app/app.sh" ]
