FROM kong/kong-gateway:3.4

USER root

# Runtime stage of the kong weblog: install curl once, so that weblog builds don't depend on the Ubuntu mirrors
RUN apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 update \
 && apt-get install -y --no-install-recommends curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
