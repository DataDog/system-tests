ARG LIB_INIT_ENV=prod

FROM docker.io/datadog/dd-lib-java-init:latest as dd-lib-init_prod

FROM ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot as dd-lib-init_dev


FROM dd-lib-init_${LIB_INIT_ENV} as dd-lib-java-init

FROM alpine:latest
RUN apk --no-cache add openjdk11 --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
RUN apk add --no-cache bash
COPY . .
RUN ./gradlew build
RUN echo 
COPY --from=dd-lib-java-init /datadog-init /datadog-lib/
ENV JAVA_TOOL_OPTIONS="-javaagent:/datadog-lib/dd-java-agent.jar"
ENV CI_USE_TEST_AGENT="true"
ENV server.port=18080
ENTRYPOINT ["java", "-jar", "build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]