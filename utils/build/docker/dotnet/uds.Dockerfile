FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /app

# `binutils` is required by 'install_ddtrace.sh' to call 'strings' command
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y binutils

COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries/* /binaries/
RUN /binaries/install_ddtrace.sh

# dotnet restore
COPY utils/build/docker/dotnet/weblog/app.csproj app.csproj

RUN DDTRACE_VERSION=$(cat /app/SYSTEM_TESTS_LIBRARY_VERSION | sed -n -E "s/.*([0-9]+.[0-9]+.[0-9]+).*/\1/p") \
    dotnet restore

# dotnet publish
COPY utils/build/docker/dotnet/weblog/* .

RUN DDTRACE_VERSION=$(cat /app/SYSTEM_TESTS_LIBRARY_VERSION | sed -n -E "s/.*([0-9]+.[0-9]+.[0-9]+).*/\1/p") \
    dotnet publish --no-restore -c Release -f net8.0 -o out

#########

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl

# Enable Datadog .NET SDK
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}'
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# Datadog .NET SDK config
ENV DD_IAST_REQUEST_SAMPLING=100
ENV DD_IAST_VULNERABILITIES_PER_REQUEST=100
ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_DATA_STREAMS_ENABLED=true
ENV DD_INTERNAL_TELEMETRY_V2_ENABLED=true

# .NET runtime config
ENV ASPNETCORE_hostBuilder__reloadConfigOnChange=false
# - Enable dump on crash
ENV COMPlus_DbgEnableMiniDump=1
# - MiniDumpWithPrivateReadWriteMemory is 2
ENV COMPlus_DbgMiniDumpType=2

COPY --from=build /app/out .
COPY --from=build /app/SYSTEM_TESTS_*_VERSION /app/
COPY --from=build /opt/datadog /opt/datadog

COPY utils/build/docker/dotnet/weblog/app.sh app.sh
CMD [ "./app.sh" ]

# The lines above is a copy of poc.Dockerfile
# The lines below are added for the UDS version only

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y socat
ENV UDS_WEBLOG=1
ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh
