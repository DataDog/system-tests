FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build

WORKDIR /src
COPY utils/build/docker/dotnet_otel/poc-otel/app.csproj .
RUN dotnet restore
COPY utils/build/docker/dotnet_otel/poc-otel/Program.cs .
RUN dotnet publish -c Release -o /out

FROM mcr.microsoft.com/dotnet/aspnet:8.0

ARG OTEL_DOTNET_AUTO_VERSION=v1.12.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# Upstream automatic instrumentation, installed the way the project documents it. OTEL_DOTNET_AUTO_HOME
# has to be set before the install script runs, it does not default to anything useful.
ENV OTEL_DOTNET_AUTO_HOME=/otel-dotnet-auto
RUN curl -sSfL "https://github.com/open-telemetry/opentelemetry-dotnet-instrumentation/releases/download/${OTEL_DOTNET_AUTO_VERSION}/otel-dotnet-auto-install.sh" -o /tmp/otel-dotnet-auto-install.sh \
    && OTEL_DOTNET_AUTO_HOME=/otel-dotnet-auto sh /tmp/otel-dotnet-auto-install.sh \
    && rm /tmp/otel-dotnet-auto-install.sh \
    && ls /otel-dotnet-auto

WORKDIR /app
COPY binaries* /binaries/
COPY --from=build /out /app
COPY utils/build/docker/dotnet_otel/poc-otel/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV OTEL_DOTNET_AUTO_VERSION=${OTEL_DOTNET_AUTO_VERSION}
ENV OTEL_SERVICE_NAME=weblog
ENV ASPNETCORE_URLS=http://0.0.0.0:7777

EXPOSE 7777

CMD ["/app/app.sh"]
