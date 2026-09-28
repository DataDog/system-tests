FROM public.ecr.aws/lambda/python:3.13

RUN dnf install -y unzip findutils socat

# Add the Datadog Extension
RUN mkdir -p /opt/extensions
COPY --from=public.ecr.aws/datadog/lambda-extension:latest /opt/. /opt/
