FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-11 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

COPY ./utils/build/docker/java/play/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/play/app ./app
COPY ./utils/build/docker/java/play/conf ./conf
COPY ./utils/build/docker/java/iast-common/src /iast-common/src
RUN mvn -Dmaven.repo.local=/maven play2:routes-compile package play2:dist-exploded

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

FROM public.ecr.aws/docker/library/eclipse-temurin:11-jre

WORKDIR /app
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/target/dist/play-app-1.0.0 .
COPY --from=build /dd-tracer/dd-java-agent.jar .

COPY ./utils/build/docker/java/app-play.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true

CMD [ "/app/app.sh" ]
