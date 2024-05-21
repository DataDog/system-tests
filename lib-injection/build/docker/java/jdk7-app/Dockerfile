FROM openjdk:7-alpine

COPY . .
RUN javac *.java
ENTRYPOINT ["java", "-cp", ".", "sunhttpd"]