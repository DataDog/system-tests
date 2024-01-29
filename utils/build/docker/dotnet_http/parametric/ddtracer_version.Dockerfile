
FROM mcr.microsoft.com/dotnet/sdk:8.0

RUN apt-get update && apt-get install dos2unix
USER root
WORKDIR /app

COPY install_ddtrace.sh query-versions.fsx binaries* /binaries/
RUN dos2unix /binaries/install_ddtrace.sh
RUN /binaries/install_ddtrace.sh

CMD cat SYSTEM_TESTS_LIBRARY_VERSION
