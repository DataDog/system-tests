FROM mcr.microsoft.com/dotnet/aspnet:2.1-stretch-slim AS base
WORKDIR /app

FROM mcr.microsoft.com/dotnet/sdk:7.0.100 AS build
WORKDIR /app
COPY . .
RUN dotnet publish -c Release -o /publish

FROM base AS final
WORKDIR /app
EXPOSE 18080
ENV ASPNETCORE_URLS=http://+:18080
COPY --from=build /publish .

ENTRYPOINT ["dotnet", "MinimalWebApp.dll"]