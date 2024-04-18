FROM alpine:latest
RUN apk --no-cache add openjdk11 --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
RUN apk add --no-cache bash
COPY . .
RUN ./gradlew build
RUN echo 
#ENTRYPOINT ["java", "-jar", "build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]
CMD [ "app.sh" ]



