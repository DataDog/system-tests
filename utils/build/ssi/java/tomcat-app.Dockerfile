ARG BASE_IMAGE

FROM 235494822917.dkr.ecr.us-east-1.amazonaws.com/third-party/maven:3.5.3-jdk-8-alpine as build
WORKDIR /app
COPY lib-injection/build/docker/java/enterprise/ ./
RUN mvn clean package

FROM ${BASE_IMAGE}
COPY --from=build app/payment-service/target/payment-service*.war /usr/local/tomcat/webapps/
ENV WEBLOG_URL=http://localhost:8080/payment-service/
ENV DD_INSTRUMENT_SERVICE_WITH_APM=true