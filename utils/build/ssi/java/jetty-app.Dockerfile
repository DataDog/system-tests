#syntax=docker/dockerfile:1.4
ARG BASE_IMAGE

FROM ${BASE_IMAGE}

RUN wget https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/9.4.56.v20240826/jetty-distribution-9.4.56.v20240826.tar.gz
RUN tar -xvf jetty-distribution-9.4.56.v20240826.tar.gz

RUN mkdir -p jetty-classpath
RUN find jetty-distribution-9.4.56.v20240826/lib -iname '*.jar' -exec cp \{\} jetty-classpath/ \;

# Causes ClassNotFound exceptions https://github.com/jetty/jetty.project/issues/4746
RUN rm jetty-classpath/jetty-jaspi*

COPY lib-injection/build/docker/java/jetty-app/ .
RUN javac -cp "jetty-classpath/*" JettyServletMain.java CrashServlet.java
RUN mkdir -p /opt/antithesis/catalog
RUN ln -s /workdir /opt/antithesis/catalog/app

# Uncomment this to use the antithesis coverage instrumentation
RUN ln -s /opt/datadog-packages/datadog-apm-library-java/1.55.0 /opt/antithesis/catalog/dd-agent

#Antithesis need one jar in the run folder to instrument the directory. In our case we have a class file in the directory, so we need to copy one of the jars (as dummy) to the run folder.
RUN cp $(ls jetty-classpath/*.jar | head -n 1) .

# Add Antithesis FFI instrumentation to dd-java-agent.jar
RUN wget https://repo1.maven.org/maven2/com/antithesis/ffi/1.4.4/ffi-1.4.4.jar -O antithesis-ffi-1.4.4.jar

# Create temporary directories for unzipping
RUN mkdir -p /tmp/dd-agent-unzipped /tmp/antithesis-unzipped

# Unzip dd-java-agent.jar
RUN unzip -q /opt/datadog-packages/datadog-apm-library-java/1.55.0/dd-java-agent.jar -d /tmp/dd-agent-unzipped

# Unzip antithesis-ffi jar
RUN unzip -q antithesis-ffi-1.4.4.jar -d /tmp/antithesis-unzipped

# List contents to debug (can be removed later)
RUN echo "Contents of antithesis jar:" && find /tmp/antithesis-unzipped -type f

# Copy com directory and all .so files from antithesis into dd-agent
RUN if [ -d /tmp/antithesis-unzipped/com ]; then cp -r /tmp/antithesis-unzipped/com /tmp/dd-agent-unzipped/; fi && \
    find /tmp/antithesis-unzipped -name "*.so" -exec cp {} /tmp/dd-agent-unzipped/ \;

# Re-zip the modified dd-java-agent.jar
RUN cd /tmp/dd-agent-unzipped && \
    zip -qr /opt/datadog-packages/datadog-apm-library-java/1.55.0/dd-java-agent.jar .

# Clean up temporary directories
RUN rm -rf /tmp/dd-agent-unzipped /tmp/antithesis-unzipped antithesis-ffi-1.4.4.jar

# https://antithesis.com/docs/using_antithesis/sdk/go/instrumentor/#coverage-instrumentation-behavior
#The Antithesis instrumentor will output a file ending in .sym.tsv. This file should be copied into a directory named /symbols in the root of the appropriate container image.
COPY utils/build/ssi/java/resources/jetty/go-285b1c98f1c9.sym.tsv ../symbols/

COPY utils/build/ssi/java/resources/jetty/antithesis_entry_point.sh .
RUN mkdir -p ../symbols

#Here the Antithesis coverage instrumentation is enabled

# End of Antithesis coverage instrumentation
CMD [ "./antithesis_entry_point.sh" ]