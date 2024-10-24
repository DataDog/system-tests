
FROM eclipse-temurin:8 as agent

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM ghcr.io/graalvm/native-image-community:21.0.0 as build

# Install maven
RUN curl https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz --output /opt/maven.tar.gz && \
	tar xzvf /opt/maven.tar.gz --directory /opt && \
	rm /opt/maven.tar.gz

WORKDIR /app

# Copy application sources and cache dependencies
COPY ./utils/build/docker/java/spring-boot-3-native/pom.xml .
RUN /opt/apache-maven-3.8.6/bin/mvn -P native -B dependency:go-offline
COPY ./utils/build/docker/java/spring-boot-3-native/src ./src

# Copy tracer
COPY --from=agent /dd-tracer/dd-java-agent.jar .

# Build native application
RUN /opt/apache-maven-3.8.6/bin/mvn -Pnative,with-profiling native:compile
RUN /opt/apache-maven-3.8.6/bin/mvn -Pnative,without-profiling native:compile

FROM ubuntu

RUN apt-get update && apt-get install -y curl

WORKDIR /app
COPY --from=agent /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/with-profiling/myproject ./with-profiling/
COPY --from=build /app/without-profiling/myproject ./without-profiling/

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

COPY ./utils/build/docker/java/app-native-profiling.sh app.sh
RUN chmod +x app.sh
CMD [ "/app/app.sh" ]
