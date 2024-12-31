ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

COPY lib-injection/build/docker/dotnet/dd-lib-dotnet-init-test-app/ .

RUN dotnet restore
RUN dotnet build -c Release

ENV ASPNETCORE_URLS=http://+:18080
EXPOSE 18080
CMD [ "dotnet", "run", "--no-build", "--no-restore", "-c", "Release" ]