FROM maven:3.5.3-jdk-8-alpine as build

WORKDIR /app
#COPY apps/java/enterprise/ ./
COPY --from=lib_injection java/enterprise/ ./
RUN mvn clean package

FROM tomcat:9
ENV DD_INSTALL_ONLY=true
ENV DD_API_KEY=abc
ENV DD_APM_INSTRUMENTATION_ENABLED=host
ENV DD_APM_INSTRUMENTATION_LIBRARIES=java
RUN /bin/bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"
COPY --from=build app/payment-service/target/payment-service*.war /usr/local/tomcat/webapps/

COPY ./base/install_script_ssi.sh ./

ARG DD_API_KEY=deadbeef
ENV DD_API_KEY=${DD_API_KEY}

ENV DD_APM_INSTRUMENTATION_LIBRARIES=java
RUN ./install_script_ssi.sh

ENV DD_INSTRUMENT_SERVICE_WITH_APM=true
ENV DD_APM_INSTRUMENTATION_DEBUG=true
ENV WEBLOG_URL=http://localhost:8080/payment-service/
COPY base/healthcheck.sh /

#COPY scripts/process /opt/datadog-packages/datadog-apm-inject/stable/inject/process
RUN echo "TEST3"