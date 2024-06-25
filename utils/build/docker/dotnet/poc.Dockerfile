FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /app

# `binutils` is required by 'install_ddtrace.sh' to call 'strings' command
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y binutils

COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries/* /binaries/
RUN /binaries/install_ddtrace.sh

# dotnet restore
COPY utils/build/docker/dotnet/weblog/app.csproj app.csproj

RUN DDTRACE_VERSION=$(cat /app/SYSTEM_TESTS_LIBRARY_VERSION | sed -n -E "s/.*([0-9]+.[0-9]+.[0-9]+).*/\1/p") && \
    dotnet restore

# dotnet publish
COPY utils/build/docker/dotnet/weblog/* .

RUN DDTRACE_VERSION=$(cat /app/SYSTEM_TESTS_LIBRARY_VERSION | sed -n -E "s/.*([0-9]+.[0-9]+.[0-9]+).*/\1/p") && \
    dotnet publish --no-restore -c Release -o out

#########

FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS runtime
WORKDIR /app

COPY --from=build /app/out .
COPY --from=build /app/SYSTEM_TESTS_*_VERSION /app/
COPY --from=build /opt/datadog /opt/datadog

COPY utils/build/docker/dotnet/weblog/app.sh app.sh
CMD [ "./app.sh" ]