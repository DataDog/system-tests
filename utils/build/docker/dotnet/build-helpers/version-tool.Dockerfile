FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-version-tool
WORKDIR /app
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
COPY utils/build/docker/dotnet/GetAssemblyVersion ./
RUN dotnet publish -c Release -o /out
