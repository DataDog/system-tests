ARG APM_LIBRARY_IMAGE=apm_library_latest

FROM ghcr.io/datadog/dd-trace-dotnet/dd-trace-dotnet:latest as agent_latest

FROM bash as apm_library_local
COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /
RUN dos2unix /install_ddtrace.sh
RUN /install_ddtrace.sh

FROM $APM_LIBRARY_IMAGE as apm_library

FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build

RUN apt-get update && apt-get install dos2unix

WORKDIR /app

COPY utils/build/docker/dotnet/app.csproj app.csproj

COPY utils/build/docker/dotnet/*.cs ./
COPY utils/build/docker/dotnet/Dependencies/*.cs ./Dependencies/
COPY utils/build/docker/dotnet/Endpoints/*.cs ./Endpoints/
COPY utils/build/docker/dotnet/Controllers/*.cs ./Controllers/
COPY utils/build/docker/dotnet/Models/*.cs ./Models/

COPY --from=apm_library /LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=apm_library /LIBDDWAF_VERSION /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=apm_library /APPSEC_EVENT_RULES_VERSION /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

COPY --from=apm_library /*.tar.gz /binaries/datadog-dotnet-apm.tar.gz
RUN mkdir -p /opt/datadog && tar xzf $(ls /binaries/datadog-dotnet-apm.tar.gz) -C /opt/datadog

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
COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
ENV DD_DATA_STREAMS_ENABLED=true
ENV UDS_WEBLOG=1

CMD [ "./app.sh" ]
