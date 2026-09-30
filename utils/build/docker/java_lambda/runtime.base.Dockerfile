# Pinned by digest (not just :17): AWS moves this tag in place for runtime/OS/security
# updates, and the base-image content hash only covers local build-context files, so a
# floating tag would freeze silently on first build and never refresh. Bumped
# automatically by .github/workflows/update-lambda-extension.yml.
FROM public.ecr.aws/lambda/java:17@sha256:9456afa5907a7531ea4f6c44ba1fa220b50a5e065068b9645e3391133a41224e

# Install only runtime dependencies
RUN yum install -y unzip findutils socat && yum clean all

# Add Datadog Extension
# Pinned (not :latest): the base-image content hash only covers local build-context
# files, so a floating tag would freeze silently on first build and never refresh.
# Bump this manually (or via .github/workflows/update-lambda-extension.yml) to pick
# up newer extension releases.
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:100 /opt/. /opt/
