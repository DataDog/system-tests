FROM alpine:latest
RUN apk --no-cache add openjdk11 --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
RUN apk add --no-cache bash
COPY build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /usr/local/app/

#UNCOMENT THESE LINES TO TEST WITH CMD
#COPY docker_entrypoint_docker.sh /usr/local/app/
#RUN chmod 755 /usr/local/app/docker_entrypoint_docker.sh
#CMD [ "/usr/local/app/docker_entrypoint_docker.sh" ]

#COMMENT THESE LINES TO TEST WITH CMD
WORKDIR /usr/local/app/
ENTRYPOINT ["java", "-jar", "k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]



