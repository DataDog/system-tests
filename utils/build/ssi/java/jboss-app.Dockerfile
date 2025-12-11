ARG BASE_IMAGE

FROM 235494822917.dkr.ecr.us-east-1.amazonaws.com/third-party/maven:3.8.3-jdk-11-slim as build
WORKDIR /app
COPY lib-injection/build/docker/java/enterprise/ ./
RUN mvn clean package

FROM ${BASE_IMAGE}
USER jboss
COPY --from=build app/ee-app-ear/target/ee-app.ear /opt/jboss/wildfly/standalone/deployments/
ENV WEBLOG_URL=http://localhost:8080/payment-service/
ENV DD_APM_INSTRUMENTATION_DEBUG=true