FROM eclipse-temurin:11-jre

# Install the UDS transport once when publishing the base image, rather than in
# every weblog build. Fail if package indexes cannot be downloaded.
RUN apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 update \
 && apt-get install -y --no-install-recommends socat \
 && rm -rf /var/lib/apt/lists/*
