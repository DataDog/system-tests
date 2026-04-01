FROM rust:1.94.1-slim-bookworm AS builder

RUN apt-get update && apt-get install -y openssh-client git && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/app
COPY utils/build/docker/rust/axum .
COPY utils/build/docker/rust/install_ddtrace.sh /binaries/install_ddtrace.sh

# Copy optional local tracer binary
COPY binaries/ /binaries/

RUN /binaries/install_ddtrace.sh

# Patch crates.io deps to use the local libdatadog sources, avoiding duplicate
# crate versions that arise when libdd-data-pipeline (path dep) and
# datadog-opentelemetry (crates.io dep) each pull a different copy of libdd-trace-utils.
RUN cat >> Cargo.toml <<'EOF'

[patch.crates-io]
libdd-trace-utils  = { path = "/binaries/libdatadog/libdd-trace-utils" }
libdd-common       = { path = "/binaries/libdatadog/libdd-common" }
libdd-tinybytes    = { path = "/binaries/libdatadog/libdd-tinybytes" }
libdd-telemetry    = { path = "/binaries/libdatadog/libdd-telemetry" }
EOF

RUN --mount=type=cache,target=/usr/app/target/ \
    --mount=type=cache,target=/usr/local/cargo/registry/ \
    cargo build --release && cp ./target/release/weblog /usr/app/weblog

RUN bash system_tests_library_version.sh > /usr/app/SYSTEM_TESTS_LIBRARY_VERSION

FROM debian:bookworm-slim AS final

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/app/weblog /app/weblog
COPY --from=builder /usr/app/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION
COPY utils/build/docker/rust/axum/app.sh /app/app.sh
RUN chmod +x /app/app.sh

WORKDIR /app
CMD ["./app.sh"]
