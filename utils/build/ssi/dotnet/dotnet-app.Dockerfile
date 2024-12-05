ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

COPY lib-injection/build/docker/dotnet/dd-lib-dotnet-init-test-app/ .

RUN dotnet restore
RUN dotnet build -c Release

ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
ENV ASPNETCORE_URLS=http://+:18080
EXPOSE 18080
CMD [ "dotnet", "run", "-c", "Release" ]