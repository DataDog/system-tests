#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

docker pull datadog/agent:latest

for lib in ${1:-dotnet golang java nodejs php python ruby}
do
    ./build.sh $lib

    source venv/bin/activate
    ./run.sh PERFORMANCES
    DD_APPSEC_ENABLED=true ./run.sh PERFORMANCES
done
