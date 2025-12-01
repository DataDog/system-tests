FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-app
WORKDIR /app

# dotnet restore
COPY utils/build/docker/dotnet/weblog/app.csproj app.csproj
RUN dotnet restore

# dotnet publish
COPY utils/build/docker/dotnet/weblog/* .
RUN dotnet publish --no-restore -c Release -f net8.0 -o out

#########

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl

# install dd-trace-dotnet (must be done before setting LD_PRELOAD)
COPY utils/build/docker/dotnet/install_ddtrace.sh binaries/ /binaries/
RUN --mount=type=secret,id=github_token /binaries/install_ddtrace.sh

# Enable Datadog .NET SDK
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}'
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# Datadog .NET SDK config
ENV DD_IAST_REQUEST_SAMPLING=100
ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_DATA_STREAMS_ENABLED=true
ENV DD_INTERNAL_TELEMETRY_V2_ENABLED=true

# .NET runtime config
ENV ASPNETCORE_hostBuilder__reloadConfigOnChange=false
# - Enable dump on crash
ENV COMPlus_DbgEnableMiniDump=1
# - MiniDumpWithPrivateReadWriteMemory is 2
ENV COMPlus_DbgMiniDumpType=2

# copy the dotnet app (built above)
COPY --from=build-app /app/out .

COPY utils/build/docker/dotnet/weblog/app.sh app.sh
CMD [ "./app.sh" ]
