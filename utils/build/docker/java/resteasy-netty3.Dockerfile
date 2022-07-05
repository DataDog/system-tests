FROM maven:3.6-jdk-11 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY ./utils/build/docker/java/resteasy-netty3/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/resteasy-netty3/src ./src
RUN mvn -Dmaven.repo.local=/maven package

FROM adoptopenjdk:11-jre-hotspot

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/resteasy-netty3-1.0-SNAPSHOT.jar .
COPY --from=build /dd-tracer/dd-java-agent.jar .

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

RUN echo "#!/bin/bash\njava -Xmx362m -javaagent:/app/dd-java-agent.jar -jar /app/resteasy-netty3-1.0-SNAPSHOT.jar" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
