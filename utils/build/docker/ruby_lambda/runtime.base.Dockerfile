FROM public.ecr.aws/lambda/ruby:3.4

RUN dnf install -y unzip findutils socat gcc make redhat-rpm-config

# Add the Datadog Extension
# Pinned (not :latest): the base-image content hash only covers local build-context
# files, so a floating tag would freeze silently on first build and never refresh.
# Bump this manually (or via .github/workflows/update-lambda-extension.yml) to pick
# up newer extension releases.
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:100 /opt/. /opt/
