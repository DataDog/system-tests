FROM mcr.microsoft.com/dotnet/sdk:8.0
WORKDIR /app

# `binutils` is required by 'install_ddtrace.sh' to call 'strings' command
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y binutils

COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD cat /app/SYSTEM_TESTS_LIBRARY_VERSION
