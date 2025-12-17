ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

COPY lib-injection/build/docker/dotnet/dd-lib-dotnet-init-test-app/ .
ENV DD_INSTRUMENT_SERVICE_WITH_APM=false
# Dynamically set the target framework based on the installed .NET version
RUN DOTNET_VERSION=$(dotnet --version | cut -d'.' -f1,2) && \
    echo "Detected .NET version: $DOTNET_VERSION" && \
    TARGET_FRAMEWORK="net${DOTNET_VERSION}" && \
    echo "Setting target framework to: $TARGET_FRAMEWORK" && \
    sed -i "s/<TargetFramework>net[0-9]\+\.[0-9]\+<\/TargetFramework>/<TargetFramework>$TARGET_FRAMEWORK<\/TargetFramework>/g" MinimalWebApp.csproj && \
    echo "Updated MinimalWebApp.csproj:" && \
    cat MinimalWebApp.csproj

RUN dotnet restore
RUN dotnet build -c Release
RUN dotnet publish -c Release -o .
ENV DD_INSTRUMENT_SERVICE_WITH_APM=true
ENV ASPNETCORE_URLS=http://+:18080
EXPOSE 18080
CMD [ "dotnet", "MinimalWebApp.dll" ]