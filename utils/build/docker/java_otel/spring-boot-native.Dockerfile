FROM maven:3.9.9-eclipse-temurin-17-focal

# Install required bsdtar
RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

# Copy application sources and cache dependencies
COPY ./utils/build/docker/java_otel/spring-boot-native/pom.xml .
COPY ./utils/build/docker/java_otel/spring-boot-native/src ./src

ENV OTEL_VERSION="1.38.0"
# Compile application
RUN mvn clean package

# Set up required args
RUN echo $OTEL_VERSION > SYSTEM_TESTS_LIBRARY_VERSION

RUN echo "#!/bin/bash\njava -jar target/myproject-3.0.0-SNAPSHOT.jar --server.port=7777" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
