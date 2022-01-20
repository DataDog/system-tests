#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

# set .env if exists. Allow users to keep their conf via env vars
if test -f ".env"; then
    source .env
fi

if [ -z "${DD_API_KEY:-}" ]; then
    echo "DD_API_KEY is missing in env, please add it."
    exit 1
fi

for lib in ${1:-dotnet golang php ruby java nodejs}
do
    # ./utils/scripts/load-binary.sh $lib
    # ./build.sh $lib

    docker-compose down
    docker inspect system_tests/weblog > logs/weblog_image.json
    export SYSTEM_TESTS_LIBRARY=$(cat logs/weblog_image.json | jq .[0].Config.Env | grep SYSTEM_TESTS_LIBRARY= | sed -E "s/.*=(.*)\",/\1/g")
    docker-compose -f scenarios/perfs/docker-compose.yml --project-directory . up runner
    docker-compose down
    DD_APPSEC_ENABLED=true docker-compose -f scenarios/perfs/docker-compose.yml --project-directory . up runner
    docker-compose down
done
