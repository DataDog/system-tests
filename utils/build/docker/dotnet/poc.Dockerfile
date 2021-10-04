FROM mcr.microsoft.com/dotnet/core/sdk:3.1 AS build

WORKDIR /app

COPY utils/build/docker/dotnet/app.csproj app.csproj

RUN dotnet restore

COPY utils/build/docker/dotnet/Program.cs Program.cs
COPY utils/build/docker/dotnet/Startup.cs Startup.cs

RUN dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/core/aspnet:3.1 AS runtime
WORKDIR /app
COPY --from=build /app/out .

COPY utils/build/docker/dotnet/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

#Setup Datadog APM
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER={846F5F1C-F9AE-4B07-969E-05C26BC060D8}
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_INTEGRATIONS=/opt/datadog/integrations.json
ENV DD_DOTNET_TRACER_HOME=/opt/datadog
ENV DD_TRACE_SAMPLE_RATE=0.5

CMD ["dotnet", "app.dll"]
