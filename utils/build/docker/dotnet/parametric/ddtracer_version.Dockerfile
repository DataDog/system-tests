
FROM alpine/xml
WORKDIR /client

COPY ./utils/build/docker/dotnet/parametric/ApmTestClient.csproj .

CMD echo $(xmllint --xpath 'string(//Project/ItemGroup/PackageReference[@Include="Datadog.Trace.Bundle"]/@Version)' ApmTestClient.csproj)