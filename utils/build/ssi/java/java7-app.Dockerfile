
#
# OpenJDK Java 7 JDK Dockerfile
#
ARG BASE_IMAGE

FROM public.ecr.aws/docker/library/ubuntu:trusty as java7

ENV APT_GET_UPDATE 2015-10-29
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive \
  apt-get -q -y install openjdk-7-jdk wget unzip \
  && apt-get clean
ENV JAVA_HOME /usr/lib/jvm/java-7-openjdk-arm64


FROM ${BASE_IMAGE}
WORKDIR /app
RUN apt-get install -y libglib2.0-0
COPY --from=java7 /usr/lib/jvm /usr/lib/jvm
COPY lib-injection/build/docker/java/jdk7-app/ .
RUN chmod -R 777 /usr/lib/jvm/java-7-openjdk-arm64
ENV JAVA_HOME /usr/lib/jvm/java-7-openjdk-arm64
RUN /usr/lib/jvm/java-7-openjdk-arm64/bin/javac *.java
RUN ln -s /usr/lib/jvm/java-7-openjdk-arm64/bin/java /usr/bin/java
CMD [ "java", "-cp", ".", "SimpleHttpServer" ]
