FROM alpine:latest
RUN apk --no-cache add openjdk11 --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
COPY build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /usr/local/app/
WORKDIR /usr/local/app/
ENTRYPOINT ["java", "-jar", "k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]



