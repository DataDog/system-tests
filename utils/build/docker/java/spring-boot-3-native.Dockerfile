FROM ghcr.io/graalvm/native-image-community:22.0.0 as build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY --from=maven:3.9.9-eclipse-temurin-17 /usr/share/maven /usr/share/maven

WORKDIR /app

# Copy application sources and cache dependencies
COPY ./utils/build/docker/java/spring-boot-3-native/pom.xml .
RUN /usr/share/maven/bin/mvn -P native -B dependency:go-offline
COPY ./utils/build/docker/java/spring-boot-3-native/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# Build native application
RUN /usr/share/maven/bin/mvn -Pnative,with-profiling native:compile
RUN /usr/share/maven/bin/mvn -Pnative,without-profiling native:compile

# Just use something small with glibc and curl. ubuntu:22.04 ships no curl, rockylinux:9 does.
# This avoids apt-get update/install, which leads to flakiness on mirror upgrades.
FROM rockylinux:9

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/with-profiling/myproject ./with-profiling/
COPY --from=build /app/without-profiling/myproject ./without-profiling/

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

COPY ./utils/build/docker/java/app-native-profiling.sh app.sh
RUN chmod +x app.sh
CMD [ "/app/app.sh" ]
