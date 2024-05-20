ARG RUNTIME

# We only ship the published app in the image
# so we only use ASPNET runtime as the base-image
FROM mcr.microsoft.com/dotnet/aspnet:7.0-$RUNTIME AS base
WORKDIR /app

FROM mcr.microsoft.com/dotnet/sdk:7.0.100-preview.2 AS build
WORKDIR /app
COPY MinimalWebApp.csproj .
RUN dotnet restore
COPY . .
RUN dotnet build -c Release

FROM build AS publish
RUN dotnet publish -c Release -o /publish

FROM base AS final
WORKDIR /app
EXPOSE 18080
ENV ASPNETCORE_URLS=http://+:18080
COPY --from=publish /publish .

ENTRYPOINT ["dotnet", "MinimalWebApp.dll"]