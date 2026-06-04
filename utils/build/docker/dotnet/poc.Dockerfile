FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-app
WORKDIR /app

# Copy binaries folder for local NuGet packages (for testing with local builds)
COPY binaries/ /binaries/
RUN if ls /binaries/*.nupkg 1> /dev/null 2>&1; then \
        dotnet nuget add source /binaries --name local-packages; \
    fi

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

# [DIAG do-not-merge] enable verbose tracer logs to diagnose Test_SqlServiceNameSource stall
ENV DD_TRACE_DEBUG=true
ENV DD_INTERNAL_LOG_LEVEL=debug
# [DIAG do-not-merge] enable Kestrel + ASP.NET pipeline debug logs to see connection accept events
ENV Logging__LogLevel__Default=Debug
ENV Logging__LogLevel__Microsoft.AspNetCore.Server.Kestrel=Debug
ENV Logging__LogLevel__Microsoft.AspNetCore.Hosting=Debug

# [DIAG do-not-merge] hypothesis test: .NET ThreadPool starvation on Kestrel's response-flush path
# is causing the ~5s stall on /rasp/sqli. Forcing min worker + IOCP threads to 32 should
# eliminate the starvation. If the stall disappears, root cause confirmed.
ENV DOTNET_ThreadPool_ForceMinWorkerThreads=32
ENV DOTNET_ThreadPool_ForceMinIoCompletionThreads=32

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
