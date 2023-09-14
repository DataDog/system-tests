#!/bin/bash

set -eu

version=$(xmllint --xpath 'string(//Project/ItemGroup/PackageReference[@Include="Datadog.Trace.Bundle"]/@Version)' ApmTestClient.csproj)

echo "$version" > SYSTEM_TESTS_LIBRARY_VERSION


