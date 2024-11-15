ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

#RUN printf "<?php\necho'hi';\n" > index.php
#
#CMD ["php","-S","0.0.0.0:18080"]

RUN wget https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/9.4.56.v20240826/jetty-distribution-9.4.56.v20240826.tar.gz
RUN tar -xvf jetty-distribution-9.4.56.v20240826.tar.gz
COPY lib-injection/build/docker/java/jetty-app/ .
RUN javac -cp jetty-distribution-9.4.56.v20240826/lib/*:jetty-distribution-9.4.56.v20240826/lib/annotations/*:jetty-distribution-9.4.56.v20240826/lib/apache-jsp/*:jetty-distribution-9.4.56.v20240826/lib/jaspi/*:jetty-distribution-9.4.56.v20240826//lib/logging/* JettyServletMain.java

CMD [ "java", "-cp", "jetty-distribution-9.4.56.v20240826/lib/*:jetty-distribution-9.4.56.v20240826/lib/annotations/*:jetty-distribution-9.4.56.v20240826/lib/apache-jsp/*:jetty-distribution-9.4.56.v20240826//lib/logging/*:jetty-distribution-9.4.56.v20240826//lib/ext/*:.", "JettyServletMain" ]