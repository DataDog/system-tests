ARG BASE_IMAGE

FROM 235494822917.dkr.ecr.us-east-1.amazonaws.com/third-party/maven:3.5.3-jdk-8-alpine as build
WORKDIR /app
COPY lib-injection/build/docker/java/enterprise/ ./
RUN mvn clean package


FROM ${BASE_IMAGE}
RUN ln -s /opt/IBM/WebSphere/AppServer/java/8.0/bin/java /usr/bin/java
COPY --from=build app/ee-app-ear/target/ee-app.ear /tmp/
COPY utils/build/ssi/java/resources/common/netstat.sh /tmp/
COPY utils/build/ssi/java/resources/websphere-app/ws_deploy.jacl /tmp/
RUN /bin/bash -c '/work/start_server.sh &' && \
/bin/bash -c 'while ! /tmp/netstat.sh | grep ":9043"; do sleep 1; done' && \
/bin/bash -c 'yes | /opt/IBM/WebSphere/AppServer/bin/wsadmin.sh -f /tmp/ws_deploy.jacl -user wsadmin -password $(cat /tmp/PASSWORD) -lang jacl' && \
/bin/bash -c '/opt/IBM/WebSphere/AppServer/bin/stopServer.sh server1 -user wsadmin -password $(cat /tmp/PASSWORD)'
ENV WEBLOG_URL=http://localhost:9080/payment-service/
ENV DD_APM_INSTRUMENTATION_DEBUG=true