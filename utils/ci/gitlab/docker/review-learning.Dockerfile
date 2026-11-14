# Image of the monthly review_learning job (see .gitlab-ci.yml and docs/ai/review-learning.md).
# It holds the tools of the review-learn skill: Python 3.12, the Claude Code CLI, gh, se, and dd-octo-sts.
# It does not hold the Python packages of system-tests: the job installs requirements.txt when it starts.
# So the tag only hashes this file, and a change to requirements.txt never rebuilds this image.

# se needs Ruby 3.3 or later. Ubuntu noble has 3.2, so take Ruby 3.4 from the Datadog Ruby image (Debian 12).
FROM registry.ddbuild.io/system-tests/mirror/ghcr.io/datadog/images-rb/engines/ruby:3.4-gnu-gcc@sha256:4739546bda4addb0a8a7d2236e598310457a45cd315d508094bee72a00ef3e19 AS ruby
RUN gem install --no-document simple_english -v 0.12.0

FROM registry.ddbuild.io/images/docker:29.4.0-noble
USER root

RUN apt update && apt install software-properties-common -y && add-apt-repository ppa:deadsnakes/ppa -y
RUN clean-apt install ca-certificates curl git jq python3.12 python3.12-venv python3.12-dev build-essential \
    libyaml-0-2 libffi8 libgmp10 zlib1g

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && clean-apt install nodejs
RUN npm install -g @anthropic-ai/claude-code@2.1.312

# Copy Ruby and its gems from the first stage.
# Debian 12 has an older glibc than noble, so the binaries run here.
COPY --from=ruby /usr/local/bin/ /usr/local/bin/
COPY --from=ruby /usr/local/lib/ /usr/local/lib/
COPY --from=ruby /usr/local/etc/ /usr/local/etc/
COPY --from=ruby /usr/local/bundle/ /usr/local/bundle/
ENV GEM_HOME=/usr/local/bundle
ENV PATH=/usr/local/bundle/bin:$PATH

ARG GH_VERSION=2.103.3
ARG TARGETARCH
RUN curl --retry 5 -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${TARGETARCH}.tar.gz" \
      | tar -xz -C /tmp && \
    mv "/tmp/gh_${GH_VERSION}_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh && \
    rm -rf "/tmp/gh_${GH_VERSION}_linux_${TARGETARCH}"

COPY --from=registry.ddbuild.io/dd-octo-sts:v1.9.3@sha256:f8412df42db2e1879182c820ea4ef600ab4375c5b696a24151c7f0dd931ffee6 /usr/local/bin/dd-octo-sts /usr/local/bin/dd-octo-sts

# If a tool is missing or broken, the build fails.
RUN python3.12 --version && ruby --version && se --help >/dev/null && gh --version && claude --version && dd-octo-sts version
