# Install curl once when publishing the base image, rather than in every weblog
# build. Fail if package indexes cannot be downloaded.
FROM kong/kong-gateway:3.4

USER root

RUN apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 update \
 && apt-get install -y --no-install-recommends curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
