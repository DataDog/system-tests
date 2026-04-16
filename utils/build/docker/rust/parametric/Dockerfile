FROM rust:1.85.1-slim-bookworm AS builder
WORKDIR /usr/app
COPY utils/build/docker/rust/parametric .
COPY utils/build/docker/rust/parametric/../install_ddtrace.sh ./binaries/ /binaries/
COPY utils/build/docker/rust/parametric/Cargo.toml /usr/app/

RUN apt-get update && apt-get install -y --no-install-recommends openssh-client git gcc

RUN /binaries/install_ddtrace.sh

RUN \
    --mount=type=cache,target=/usr/app/target/ \
    --mount=type=cache,target=/usr/local/cargo/registry/ \
    cargo build --release && cp ./target/release/ddtrace-rs-client /usr/app

# Build locale_init.so in the builder (gcc already present)
RUN printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c

FROM debian:bookworm-slim AS final
COPY --from=builder /usr/app/ddtrace-rs-client /usr/app/ddtrace-rs-client
COPY --from=builder /usr/app/Cargo.lock /usr/app/Cargo.lock
COPY --from=builder /locale_init.so /locale_init.so
COPY utils/build/docker/rust/parametric/system_tests_library_version.sh /usr/app/system_tests_library_version.sh

# Install locales and bash in the final stage
RUN apt-get update && apt-get install -y --no-install-recommends locales bash \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /parametric-tracer-logs
WORKDIR /usr/app

CMD ["bash", "-c", "[ -n \"${TEST_LOCALE:-}\" ] && export LD_PRELOAD=/locale_init.so; exec ./ddtrace-rs-client"]
