

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
RUN apt-get update && apt-get install -y dos2unix --no-install-recommends
RUN apt-get update && apt-get install -y curl
USER root
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry (prevent unexpected http client spans)
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# Set up automatic instrumentation (required for OpenTelemetry tests),
# but don't enable it globally
ENV CORECLR_ENABLE_PROFILING=0
ENV CORECLR_PROFILER={846F5F1C-F9AE-4B07-969E-05C26BC060D8}
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# disable gRPC, ASP.NET Core, and other auto-instrumentations (to prevent unexpected spans)
ENV DD_TRACE_Grpc_ENABLED=false
ENV DD_TRACE_AspNetCore_ENABLED=false
ENV DD_TRACE_Process_ENABLED=false
ENV DD_TRACE_OTEL_ENABLED=false

# ensure that the Datadog.Trace.dlls are installed from /binaries
COPY /install_ddtrace.sh /query-versions.fsx binaries* /binaries/
RUN dos2unix /binaries/install_ddtrace.sh
RUN /binaries/install_ddtrace.sh

RUN ls /binaries

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src

# restore nuget packages
COPY ["ApmTestApi.csproj", "nuget.config", "*.nupkg", "./"]
RUN dotnet restore "./././ApmTestApi.csproj"

COPY . .
WORKDIR "/src/."
RUN dotnet build "./ApmTestApi.csproj" -c $BUILD_CONFIGURATION -o /app/build

FROM build AS publish
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "./ApmTestApi.csproj" -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "ApmTestApi.dll"]
