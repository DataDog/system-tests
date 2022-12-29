FROM maven:3.8-jdk-11 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools build-essential 

WORKDIR /app

RUN curl -sL https://github.com/graalvm/graalvm-ce-builds/releases/download/vm-22.3.0/graalvm-ce-java11-linux-amd64-22.3.0.tar.gz --output graalvm-ce-java11-linux-amd64-22.3.0.tar.gz 
RUN tar -xzf graalvm-ce-java11-linux-amd64-22.3.0.tar.gz 

ENV PATH="/app/graalvm-ce-java11-22.3.0/bin:$PATH"
ENV GRAALVM_HOME="/app/graalvm-ce-java11-22.3.0"

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline -P spring-native

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Dmaven.repo.local=/maven package -P spring-native

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh

FROM adoptopenjdk:11-jre-hotspot

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar .
COPY --from=build /dd-tracer/dd-java-agent.jar .

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

RUN echo "#!/bin/bash\njava -Xmx362m -javaagent:/app/dd-java-agent.jar -jar /app/myproject-0.0.1-SNAPSHOT.jar --server.port=7777 " > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
