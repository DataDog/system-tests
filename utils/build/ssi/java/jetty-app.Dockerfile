#syntax=docker/dockerfile:1.4
ARG BASE_IMAGE

FROM ${BASE_IMAGE}

RUN wget https://static.datadoghq.com/assets/dd-repo-tools/mirror/02f5f9c4f6b4be0e5b2640d4b5a21e2838d68143ef96c540c2ba39885b60cb62/jetty-distribution-9.4.56.v20240826.tar.gz
RUN tar -xvf jetty-distribution-9.4.56.v20240826.tar.gz

RUN mkdir -p jetty-classpath
RUN find jetty-distribution-9.4.56.v20240826/lib -iname '*.jar' -exec cp \{\} jetty-classpath/ \;

# Causes ClassNotFound exceptions https://github.com/jetty/jetty.project/issues/4746
RUN rm jetty-classpath/jetty-jaspi*

COPY lib-injection/build/docker/java/jetty-app/ .
RUN javac -cp "jetty-classpath/*" JettyServletMain.java CrashServlet.java

CMD [ "java", "-XX:+UseParallelGC","-cp", "jetty-classpath/*:.", "JettyServletMain" ]
