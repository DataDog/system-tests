FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-app
WORKDIR /app

# dotnet restore
COPY utils/build/docker/dotnet_otel/app.csproj app.csproj
RUN dotnet restore

# After restore, set the BUILD_OTEL_SDK environment variable to determine how to build the app
# Set BUILD_OTEL_SDK=true to include the OpenTelemetry SDK in the app
# Otherwise, only the OpenTelemetry API will be included
# ENV BUILD_OTEL_SDK=true

# dotnet publish
COPY utils/build/docker/dotnet_otel/* .
RUN dotnet publish --no-restore -c Release -f net8.0 -o out

#########

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl

# install dd-trace-dotnet (must be done before setting LD_PRELOAD)
COPY utils/build/docker/dotnet/install_ddtrace.sh binaries/ /binaries/
RUN --mount=type=secret,id=github_token /binaries/install_ddtrace.sh

# OpenTelemetry SDK config
# ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_SAMPLER=always_on
ENV OTEL_BSP_MAX_QUEUE_SIZE=1
ENV OTEL_BSP_MAX_EXPORT_BATCH_SIZE=1

# Enable Datadog .NET SDK
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}'
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog
ENV DD_TRACE_DEBUG=true

# Datadog SDK config
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/json

# Combined OTEL and Datadog .NET SDK config
ENV OTEL_SERVICE_NAME=weblog-otel
ENV OTEL_RESOURCE_ATTRIBUTES=deployment.environment=system-tests
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://proxy:8127
ENV OTEL_EXPORTER_OTLP_HEADERS=dd-protocol=otlp,dd-otlp-path=agent

# .NET runtime config
ENV ASPNETCORE_hostBuilder__reloadConfigOnChange=false
# - Enable dump on crash
ENV COMPlus_DbgEnableMiniDump=1
# - MiniDumpWithPrivateReadWriteMemory is 2
ENV COMPlus_DbgMiniDumpType=2

# copy the dotnet app (built above)
COPY --from=build-app /app/out .

COPY utils/build/docker/dotnet_otel/app.sh app.sh
CMD [ "./app.sh" ]
