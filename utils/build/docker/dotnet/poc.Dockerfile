FROM mcr.microsoft.com/dotnet/core/sdk:3.1 AS build

RUN apt-get update && apt-get install dos2unix

WORKDIR /app

COPY utils/build/docker/dotnet/app.csproj app.csproj

RUN dotnet restore

COPY utils/build/docker/dotnet/*.cs ./
COPY utils/build/docker/dotnet/Dependencies/*.cs ./Dependencies/
COPY utils/build/docker/dotnet/Endpoints/*.cs ./Endpoints/
COPY utils/build/docker/dotnet/Controllers/*.cs ./Controllers/
COPY utils/build/docker/dotnet/Models/*.cs ./Models/

COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /binaries/
RUN dos2unix /binaries/install_ddtrace.sh
RUN /binaries/install_ddtrace.sh

RUN dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/core/aspnet:3.1 AS runtime
WORKDIR /app
COPY --from=build /app/out .

RUN mkdir /opt/datadog
COPY --from=build /opt/datadog /opt/datadog

COPY --from=build /app/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/SYSTEM_TESTS_LIBDDWAF_VERSION /app/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

#Setup Datadog APM
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER={846F5F1C-F9AE-4B07-969E-05C26BC060D8}
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_INTEGRATIONS=/opt/datadog/integrations.json
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

RUN echo "#!/bin/bash\ndotnet app.dll" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]

