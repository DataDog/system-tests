ARG TRACER_IMAGE=agent_local

FROM ghcr.io/datadog/dd-trace-dotnet/dd-trace-dotnet:latest_snapshot as agent_latest_snapshot

FROM ghcr.io/datadog/dd-trace-dotnet/dd-trace-dotnet:latest as agent_latest

FROM bash as agent_local
COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /
RUN dos2unix /install_ddtrace.sh
RUN /install_ddtrace.sh

FROM $TRACER_IMAGE as agent


FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build

RUN apt-get update && apt-get install dos2unix

WORKDIR /app

COPY utils/build/docker/dotnet/app.csproj app.csproj

COPY utils/build/docker/dotnet/*.cs ./
COPY utils/build/docker/dotnet/Dependencies/*.cs ./Dependencies/
COPY utils/build/docker/dotnet/Endpoints/*.cs ./Endpoints/
COPY utils/build/docker/dotnet/Controllers/*.cs ./Controllers/
COPY utils/build/docker/dotnet/Models/*.cs ./Models/

COPY --from=agent /LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /LIBDDWAF_VERSION /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /APPSEC_EVENT_RULES_VERSION /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

COPY --from=agent /*.tar.gz /binaries/
RUN tar xzf $(ls /binaries/datadog-dotnet-apm-*.tar.gz) -C /opt/datadog

RUN DDTRACE_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION | sed -n -E "s/.*([0-9]+.[0-9]+.[0-9]+).*/\1/p") dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS runtime

WORKDIR /app
COPY --from=build /app/out .

RUN mkdir /opt/datadog
COPY --from=build /opt/datadog /opt/datadog

COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION /app/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=build /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

COPY utils/build/docker/dotnet/app.sh app.sh
ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_DATA_STREAMS_ENABLED=true

CMD [ "./app.sh" ]

