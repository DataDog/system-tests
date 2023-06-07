
FROM mcr.microsoft.com/dotnet/sdk:7.0
WORKDIR /client

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
COPY ["./ApmTestClient.csproj", "./nuget.config", "./*.nupkg", "./"]
RUN dotnet restore "./ApmTestClient.csproj"
COPY . ./
RUN dotnet publish --no-restore --configuration Release --output out
WORKDIR /client/out

# Opt-out of .NET SDK CLI telemetry (prevent unexpected http client spans)
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# Set up automatic instrumentation (required for OpenTelemetry tests),
# but don't enable it globally
ENV CORECLR_ENABLE_PROFILING=0
ENV CORECLR_PROFILER={846F5F1C-F9AE-4B07-969E-05C26BC060D8}
ENV CORECLR_PROFILER_PATH=/client/out/datadog/linux-x64/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/client/out/datadog

# disable gRPC, ASP.NET Core, and other auto-instrumentations (to prevent unexpected spans)
ENV DD_TRACE_Grpc_ENABLED=false
ENV DD_TRACE_AspNetCore_ENABLED=false
ENV DD_TRACE_Process_ENABLED=false
