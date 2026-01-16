FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-app
WORKDIR /app

# dotnet restore
COPY utils/build/docker/dotnet_otel/app.csproj app.csproj
RUN dotnet restore

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
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://proxy:8127
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_EXPORTER_OTLP_HEADERS=dd-protocol=otlp,dd-otlp-path=agent

ENV OTEL_TRACES_SAMPLER=always_on
ENV OTEL_BSP_MAX_QUEUE_SIZE=1
ENV OTEL_BSP_MAX_EXPORT_BATCH_SIZE=1

# Enable Datadog .NET SDK
ENV CORECLR_ENABLE_PROFILING=0
ENV CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}'
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# Datadog .NET SDK config

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
