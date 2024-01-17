
FROM mcr.microsoft.com/dotnet/sdk:6.0

RUN apt-get update && apt-get install dos2unix

WORKDIR /app

COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /binaries/
RUN dos2unix /binaries/install_ddtrace.sh
RUN /binaries/install_ddtrace.sh

CMD cat SYSTEM_TESTS_LIBRARY_VERSION
