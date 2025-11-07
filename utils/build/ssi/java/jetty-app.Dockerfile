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
RUN ln -s /opt/datadog-packages/datadog-apm-library-java/1.55.0 /opt/antithesis/catalog/dd-agent
#Antithesis need one jar in the run folder to instrument the directory. In our case we have a class file in the directory, so we need to copy one of the jars (as dummy) to the run folder.
RUN cp $(ls jetty-classpath/*.jar | head -n 1) .
COPY utils/build/ssi/java/resources/jetty/antithesis_entry_point.sh .
RUN mkdir -p ../symbols
COPY utils/build/ssi/java/resources/jetty/go-285b1c98f1c9.sym.tsv ../symbols/
CMD [ "./antithesis_entry_point.sh" ]