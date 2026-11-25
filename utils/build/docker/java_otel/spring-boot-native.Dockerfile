# The base image holds a maven repository filled from spring-boot-native/pom.xml, and sets OTEL_VERSION:
# maven runs offline here
FROM system_tests_base_java_otel_java_otel_spring_boot_native

WORKDIR /app

COPY ./utils/build/docker/java_otel/spring-boot-native/pom.xml .
COPY ./utils/build/docker/java_otel/spring-boot-native/src ./src

# Compile application
RUN mvn -o -Dmaven.repo.local=/maven -B package

# Set up required args
RUN mkdir -p /binaries && echo $OTEL_VERSION > /binaries/SYSTEM_TESTS_LIBRARY_VERSION

RUN echo "#!/bin/bash\njava -jar target/myproject-3.0.0-SNAPSHOT.jar --server.port=7777" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
