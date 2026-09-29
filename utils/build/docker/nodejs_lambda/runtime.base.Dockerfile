FROM public.ecr.aws/lambda/nodejs:18

RUN yum install -y unzip findutils socat && yum clean all

# Add the Datadog Extension
# Pinned (not :latest): the base-image content hash only covers local build-context
# files, so a floating tag would freeze silently on first build and never refresh.
# Bump this manually to pick up newer extension releases.
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:100 /opt/. /opt/
