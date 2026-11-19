# The base image holds a maven repository filled from java_lambda/pom.xml: maven runs offline here
FROM system_tests_base_java_lambda_java_lambda_maven AS builder

COPY utils/build/docker/java_lambda/pom.xml .
COPY utils/build/docker/java_lambda/src ./src
COPY utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh "-o -Dmaven.repo.local=/maven"
RUN mvn -o -Dmaven.repo.local=/maven -B package -DskipTests

# Runtime image
FROM system_tests_base_java_lambda_java_lambda_runtime

COPY --from=builder /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION

# Copy built JAR and extract to Lambda task root
COPY --from=builder /app/target/java-lambda-weblog-*.jar /tmp/app.jar
RUN cd ${LAMBDA_TASK_ROOT} && jar xf /tmp/app.jar && rm /tmp/app.jar
COPY --from=builder /app/target/sca-libs/*.jar ${LAMBDA_TASK_ROOT}/lib/

# Copy Datadog agent and entrypoint
COPY --from=builder /dd-tracer/dd-java-agent.jar ${LAMBDA_TASK_ROOT}/dd-java-agent.jar
COPY utils/build/docker/java_lambda/app.sh ${LAMBDA_TASK_ROOT}/app.sh
RUN chmod +x ${LAMBDA_TASK_ROOT}/app.sh

# Environment configuration
ENV DD_LAMBDA_HANDLER=com.datadoghq.lambda.Handler::handleRequest \
    _HANDLER=com.datadoghq.lambda.Handler::handleRequest \
    SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE=apigateway-http \
    JAVA_TOOL_OPTIONS="-javaagent:/var/task/dd-java-agent.jar" \
    DD_TRACE_AGENT_URL=http://proxy:8126 \
    DD_SERVICE=weblog \
    DD_ENV=system-tests \
    DD_APPSEC_ENABLED=true \
    DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent' \
    DD_TRACE_INTERNAL_EXIT_ON_FAILURE=true \
    DD_DATA_STREAMS_ENABLED=true

LABEL system-tests.lambda-proxy.event-type=apigateway-http

ENTRYPOINT ["/var/task/app.sh"]
