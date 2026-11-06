FROM public.ecr.aws/lambda/java:17

# Install only runtime dependencies
RUN yum install -y unzip findutils socat && yum clean all

# Add Datadog Extension
# Pinned (not :latest): the base-image content hash only covers local build-context
# files, so a floating tag would freeze silently on first build and never refresh.
# Bump this manually (or via .github/workflows/update-lambda-extension.yml) to pick
# up newer extension releases.
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:100 /opt/. /opt/
