ARG BASE_IMAGE

#syntax=docker/dockerfile:1.4
FROM maven:3.9-eclipse-temurin-11 as build

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY ./utils/build/docker/java/iast-common/src /iast-common/src

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Dmaven.repo.local=/maven package

FROM ${BASE_IMAGE}

COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /workdir/app.jar

RUN mkdir -p /var/log/java

RUN echo '#!/bin/bash' > app.sh && \
    echo 'java -jar /workdir/app.jar --server.port=18080' >> app.sh && \
    chmod +x app.sh

CMD [ "./app.sh" ]


