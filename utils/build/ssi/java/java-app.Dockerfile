#syntax=docker/dockerfile:1.4
ARG BASE_IMAGE

FROM ${BASE_IMAGE}

COPY lib-injection/build/docker/java/jdk7-app/ .
RUN javac *.java

#ENTRYPOINT ["java/bin/java", "-cp", ".", "SimpleHttpServer"]
CMD [ "java", "-cp", ".", "SimpleHttpServer" ]