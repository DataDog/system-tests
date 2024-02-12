FROM maven:3.9-eclipse-temurin-11 

COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
CMD cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION  | grep -o '^[^\~]*'