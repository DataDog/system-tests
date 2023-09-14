
FROM alpine/xml
WORKDIR /client

COPY ./utils/build/docker/dotnet/parametric/ApmTestClient.csproj .
COPY ./utils/build/docker/dotnet/parametric/ddtracer_version.sh .
RUN sh ddtracer_version.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION