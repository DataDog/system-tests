FROM public.ecr.aws/docker/library/alpine:latest
RUN apk --no-cache add openjdk11 --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
RUN apk add --no-cache bash curl
COPY . .
# Maven Central rate limits CI with HTTP 429, so dependencies come from the internal Maven proxy.
ARG MAVEN_REPOSITORY_PROXY=https://depot-read-api-java.us1.ddbuild.io/magicmirror/magicmirror/@current/
# Try the internal mirrors first. If they do not answer, keep services.gradle.org and the public Maven repositories.
RUN mirror=static.datadoghq.com/assets/dd-repo-tools/mirror/6f74b601422d6d6fc4e1f9a1ab6522f642c2fdcbc15ae33ebd30ba3d7198e854 \
    && curl -fsI --max-time 20 "https://${mirror}/gradle-8.14.5-bin.zip" >/dev/null \
    && sed -i "s|services.gradle.org/distributions|${mirror}|" gradle/wrapper/gradle-wrapper.properties \
    || true; \
    if ! curl -fsSI --max-time 20 "${MAVEN_REPOSITORY_PROXY}org/springframework/boot/spring-boot-dependencies/2.7.18/spring-boot-dependencies-2.7.18.pom" >/dev/null; then \
        echo "Maven proxy ${MAVEN_REPOSITORY_PROXY} does not answer, using the public Maven repositories"; \
        unset MAVEN_REPOSITORY_PROXY; \
    fi; \
    ./gradlew build

ENV server.port=18080
ENTRYPOINT ["java", "-jar", "build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]