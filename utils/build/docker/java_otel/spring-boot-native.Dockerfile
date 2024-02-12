FROM openjdk:17-buster

# Install required bsdtar
RUN apt-get update && \
	apt-get install -y libarchive-tools


# Install maven
RUN curl https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz --output /opt/maven.tar.gz && \
	tar xzvf /opt/maven.tar.gz --directory /opt && \
	rm /opt/maven.tar.gz

WORKDIR /app

# Copy application sources and cache dependencies
COPY ./utils/build/docker/java_otel/spring-boot-native/pom.xml .
COPY ./utils/build/docker/java_otel/spring-boot-native/src ./src

ENV OTEL_VERSION="1.26.0"
# Compile application
RUN /opt/apache-maven-3.8.6/bin/mvn clean package

# Set up required args
RUN echo $OTEL_VERSION > SYSTEM_TESTS_LIBRARY_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

RUN echo "#!/bin/bash\njava -jar target/myproject-3.0.0-SNAPSHOT.jar --server.port=7777" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
