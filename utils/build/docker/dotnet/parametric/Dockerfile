
FROM mcr.microsoft.com/dotnet/sdk:6.0
WORKDIR /client
COPY ["./ApmTestClient.csproj","./nuget.config","./*.nupkg", "./"]
RUN dotnet restore "./ApmTestClient.csproj"
COPY . .
WORKDIR "/client/."
