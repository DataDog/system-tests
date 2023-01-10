FROM maven:3.8-jdk-11

RUN apt-get update && \
	apt-get install -y libarchive-tools build-essential zlib1g-dev

WORKDIR /app

RUN curl -sL https://github.com/graalvm/graalvm-ce-builds/releases/download/vm-22.3.0/graalvm-ce-java11-linux-amd64-22.3.0.tar.gz --output graalvm-ce-java11-linux-amd64-22.3.0.tar.gz 
RUN tar -xzf graalvm-ce-java11-linux-amd64-22.3.0.tar.gz 
ENV PATH="/app/graalvm-ce-java11-22.3.0/bin:$PATH"
ENV GRAALVM_HOME="/app/graalvm-ce-java11-22.3.0"

COPY pom.xml .
RUN mvn -B dependency:go-offline -P spring-native,undertow,wildfly,openliberty,jetty
RUN rm -rf pom.xml