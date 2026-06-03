#syntax=docker/dockerfile:1.4
ARG JETTY_CLASSPATH_IMAGE=datadog/system-tests:java-jetty-9.4.58.v20250814.base-v1
ARG BASE_IMAGE

FROM ${JETTY_CLASSPATH_IMAGE} AS jetty_classpath

FROM ${BASE_IMAGE}

COPY --from=jetty_classpath /opt/jetty-classpath /opt/jetty-classpath

COPY lib-injection/build/docker/java/jetty-app/ .
RUN javac -cp "/opt/jetty-classpath/*" JettyServletMain.java CrashServlet.java

CMD [ "java", "-cp", "/opt/jetty-classpath/*:.", "JettyServletMain" ]
