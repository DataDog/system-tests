FROM public.ecr.aws/docker/library/alpine:latest
RUN apk --no-cache add openjdk11 --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
RUN apk add --no-cache bash curl
COPY . .
# Try the internal mirror first. If it does not answer, keep services.gradle.org.
RUN mirror=static.datadoghq.com/assets/dd-repo-tools/mirror/6f74b601422d6d6fc4e1f9a1ab6522f642c2fdcbc15ae33ebd30ba3d7198e854 \
    && curl -fsI --max-time 20 "https://${mirror}/gradle-8.14.5-bin.zip" >/dev/null \
    && sed -i "s|services.gradle.org/distributions|${mirror}|" gradle/wrapper/gradle-wrapper.properties \
    || true \
    && ./gradlew build

ENV server.port=18080
ENTRYPOINT ["java", "-jar", "build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]