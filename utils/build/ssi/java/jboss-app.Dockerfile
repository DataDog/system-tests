ARG BASE_IMAGE

FROM maven:3.5.3-jdk-8-alpine as build
WORKDIR /app
COPY lib-injection/build/docker/java/enterprise/ ./
RUN mvn clean package

FROM ${BASE_IMAGE}
USER jboss
COPY --from=build app/ee-app-ear/target/ee-app.ear /tmp/
COPY utils/build/ssi/java/resources/common/netstat.sh /tmp/
#RUN /bin/bash -c '$JBOSS_HOME/bin/standalone.sh &' && \
#/bin/bash -c 'while ! /tmp/netstat.sh | grep "127.0.0.1:9990"; do sleep 1; done' && \
#/bin/bash -c '$JBOSS_HOME/bin/jboss-cli.sh --connect --command="deploy /tmp/ee-app.ear"' && \
#/bin/bash -c '$JBOSS_HOME/bin/jboss-cli.sh --connect --command=":shutdown"'

ENV DD_APM_INSTRUMENTATION_DEBUG=false
RUN /bin/bash -c '$JBOSS_HOME/bin/standalone.sh &'
RUN sleep 20
#/bin/bash -c 'while ! /tmp/netstat.sh | grep "127.0.0.1:9990"; do sleep 1; done' && \
RUN /bin/bash -c '$JBOSS_HOME/bin/jboss-cli.sh --connect --command="deploy /tmp/ee-app.ear"' && \
/bin/bash -c '$JBOSS_HOME/bin/jboss-cli.sh --connect --command=":shutdown"'

ENV WEBLOG_URL=http://localhost:8080/payment-service/
ENV DD_APM_INSTRUMENTATION_DEBUG=true