# The base image holds a maven repository filled from spring-boot-3-native/pom.xml: maven runs offline here
FROM system_tests_base_java_spring_boot_3_native AS build

COPY ./utils/build/docker/java/spring-boot-3-native/pom.xml .
COPY ./utils/build/docker/java/spring-boot-3-native/src ./src
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh "-o -Dmaven.repo.local=/maven"

# Build native application
RUN /usr/share/maven/bin/mvn -o -Dmaven.repo.local=/maven -B -Pnative,with-profiling native:compile
RUN /usr/share/maven/bin/mvn -o -Dmaven.repo.local=/maven -B -Pnative,without-profiling native:compile

# Just use something small with glibc and curl. ubuntu:22.04 ships no curl, rockylinux:9 does.
# This avoids apt-get update/install, which leads to flakiness on mirror upgrades.
FROM rockylinux:9

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/with-profiling/myproject ./with-profiling/
COPY --from=build /app/without-profiling/myproject ./without-profiling/

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

COPY ./utils/build/docker/java/ConfigChaining.properties /app/ConfigChaining.properties
COPY ./utils/build/docker/java/app-native-profiling.sh app.sh
RUN chmod +x app.sh
CMD [ "/app/app.sh" ]
