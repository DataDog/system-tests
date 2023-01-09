FROM ghcr.io/graalvm/graalvm-ce:ol8-java11-22

# Install maven
RUN curl https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz --output /opt/maven.tar.gz && \
	tar xzvf /opt/maven.tar.gz --directory /opt && \
	rm /opt/maven.tar.gz

WORKDIR /app

# Copy application sources
COPY pom.xml .
COPY src/ ./src
RUN mv ./src/main/resources/application-native.properties ./src/main/resources/application.properties

# Copy tracer
COPY dd-java-agent.jar .

# Build native application
RUN /opt/apache-maven-3.8.6/bin/mvn package -P spring-native
