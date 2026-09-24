FROM registry.ddbuild.io/images/docker:20.10.13-jammy

# python3 (stdlib only) to run build_ci_image.py
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*

# Install ddsign for image signing
# https://datadoghq.atlassian.net/wiki/spaces/SECENG/pages/2744681107/Image+Integrity+User+Guide
COPY --from=registry.ddbuild.io/ddsign:v1.11.10@sha256:55784668a612ab22129bb15a665a847819bfa64b9a595c59a03a3a725534ce22 /usr/local/bin/ddsign /usr/local/bin/ddsign
