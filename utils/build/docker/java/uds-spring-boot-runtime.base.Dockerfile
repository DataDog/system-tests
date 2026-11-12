FROM eclipse-temurin:11-jre

# Runtime stage of uds-spring-boot: socat is used by set-uds-transport.sh. Installing it here keeps
# `apt-get update` (and its mirror flakiness) out of weblog builds.
RUN apt-get update \
 && apt-get install socat -y \
 && rm -rf /var/lib/apt/lists/*
