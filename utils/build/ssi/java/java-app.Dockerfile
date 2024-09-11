#syntax=docker/dockerfile:1.4
ARG BASE_IMAGE

FROM ${BASE_IMAGE}

COPY lib-injection/build/docker/java/jdk7-app/ .
RUN javac *.java

CMD [ "java", "-cp", ".", "SimpleHttpServer" ]