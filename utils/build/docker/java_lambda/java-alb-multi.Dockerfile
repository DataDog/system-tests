# Multi-stage build
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY utils/build/docker/java_lambda/pom.xml .
COPY utils/build/docker/java_lambda/src ./src
RUN mvn clean package -DskipTests

# Runtime image
FROM public.ecr.aws/lambda/java:17

# Install only runtime dependencies
RUN yum install -y unzip findutils socat && yum clean all

# Add Datadog Extension
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:latest /opt/. /opt/

# Install dd-trace-java
COPY utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# Copy built JAR and extract to Lambda task root
COPY --from=builder /build/target/java-lambda-weblog-*.jar /tmp/app.jar
RUN cd ${LAMBDA_TASK_ROOT} && jar xf /tmp/app.jar && rm /tmp/app.jar

# Copy Datadog agent and entrypoint
RUN cp /dd-tracer/dd-java-agent.jar ${LAMBDA_TASK_ROOT}/dd-java-agent.jar
COPY utils/build/docker/java_lambda/app.sh ${LAMBDA_TASK_ROOT}/app.sh
RUN chmod +x ${LAMBDA_TASK_ROOT}/app.sh

# Environment configuration
ENV DD_LAMBDA_HANDLER=com.datadoghq.lambda.Handler::handleRequest \
    _HANDLER=com.datadoghq.lambda.Handler::handleRequest \
    SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE=application-load-balancer-multi \
    JAVA_TOOL_OPTIONS="-javaagent:/var/task/dd-java-agent.jar" \
    DD_TRACE_AGENT_URL=http://proxy:8126 \
    DD_SERVICE=weblog \
    DD_ENV=system-tests \
    DD_APPSEC_ENABLED=true \
    DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent' \
    DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true \
    DD_DATA_STREAMS_ENABLED=true

LABEL system-tests.lambda-proxy.event-type=application-load-balancer-multi

ENTRYPOINT ["/var/task/app.sh"]
