FROM rust:1.87-slim-bookworm AS builder
WORKDIR /usr/app

# Bring in the weblog sources.
COPY utils/build/docker/rust/weblog .

# Bring in the binaries folder, which may contain a dd-trace-rs checkout and/or a rust-load-from-git file.
COPY binaries/ /binaries/

RUN apt-get update && apt-get install -y --no-install-recommends openssh-client git jq build-essential perl libssl-dev pkg-config curl

# Resolves the dd-trace-rs source into /binaries/dd-trace-rs and stamps a -dev version (trace-only,
# no gRPC features) so this builds against the feature branch on the rust:1.87 toolchain.
RUN bash ./install_ddtrace.sh

RUN \
    --mount=type=cache,target=/usr/app/target/ \
    --mount=type=cache,target=/usr/local/cargo/registry/ \
    cargo build --release && cp ./target/release/weblog /usr/app/weblog

# Resolve the tracer version from the lockfile so the weblog can report it on /healthcheck.
RUN ./system_tests_library_version.sh > /usr/app/SYSTEM_TESTS_LIBRARY_VERSION

FROM debian:bookworm-slim AS final
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/app/weblog /usr/app/weblog
COPY --from=builder /usr/app/Cargo.lock /usr/app/Cargo.lock
COPY --from=builder /usr/app/SYSTEM_TESTS_LIBRARY_VERSION /usr/app/SYSTEM_TESTS_LIBRARY_VERSION

WORKDIR /usr/app

# The harness invokes ./app.sh; export the resolved tracer version so /healthcheck can return it.
RUN printf '#!/bin/bash\nexport SYSTEM_TESTS_LIBRARY_VERSION="$(cat /usr/app/SYSTEM_TESTS_LIBRARY_VERSION)"\nexec ./weblog\n' > app.sh \
    && chmod +x app.sh

CMD ["./app.sh"]
