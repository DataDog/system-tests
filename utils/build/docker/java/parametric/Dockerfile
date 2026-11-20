# The base image holds a maven repository filled from parametric/pom.xml: maven runs offline here
FROM system_tests_base_java_java_parametric

WORKDIR /client
RUN mkdir ./tracer
COPY utils/build/docker/java/parametric/src src
COPY utils/build/docker/java/parametric/install_ddtrace.sh .
COPY utils/build/docker/java/parametric/pom.xml .
COPY binaries /binaries
RUN bash install_ddtrace.sh
COPY utils/build/docker/java/parametric/run.sh .
RUN mkdir /parametric-tracer-logs

CMD ["./run.sh"]
