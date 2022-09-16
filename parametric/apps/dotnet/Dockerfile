
FROM mcr.microsoft.com/dotnet/sdk:6.0
WORKDIR /client
COPY ["ApmTestClient.csproj", "."]
RUN dotnet restore "./ApmTestClient.csproj"
COPY . .
WORKDIR "/client/."
