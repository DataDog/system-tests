# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

#!/bin/bash

set -e

# set .env if exists. Allow users to keep their conf via env vars
if test -f ".env"; then
    source .env
fi

CURRENT_PWD=$(pwd)

WEBLOG_VARIANT=${WEBLOG_VARIANT:-${HTTP_FRAMEWORK}}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|nodejs|php|python|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -i|--images) BUILD_IMAGES="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -e|--extra-docker-args) EXTRA_DOCKER_ARGS="$2"; shift ;;
        *) cat utils/build/README.md; exit 1 ;;
    esac
    shift
done

# default: build all images
BUILD_IMAGES=${BUILD_IMAGES:-weblog,runner,agent}

# default: node
TEST_LIBRARY=${TEST_LIBRARY:-nodejs}

if [ "$TEST_LIBRARY" = "nodejs" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-express-poc}

elif [ "$TEST_LIBRARY" = "python" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-flask-poc}

elif [ "$TEST_LIBRARY" = "ruby" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-sinatra-poc}

elif [ "$TEST_LIBRARY" = "golang" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-net-http-poc}

elif [ "$TEST_LIBRARY" = "java" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-spring-boot-poc}

elif [ "$TEST_LIBRARY" = "php" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-vanilla-poc}

elif [ "$TEST_LIBRARY" = "dotnet" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-poc}

elif [ "$TEST_LIBRARY" = "cpp" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-nginx}

else
    echo "Unknown library: ${TEST_LIBRARY}"
    cat utils/build/README.md
    exit 1
fi

echo "=================================="
echo "build images for system tests"
echo ""
echo "TEST_LIBRARY:      $TEST_LIBRARY"
echo "WEBLOG_VARIANT:    $WEBLOG_VARIANT"
echo "BUILD_IMAGES:      $BUILD_IMAGES"
echo "EXTRA_DOCKER_ARGS: $EXTRA_DOCKER_ARGS"
echo ""

# Build images
for IMAGE_NAME in $(echo $BUILD_IMAGES | sed "s/,/ /g")
do
    echo Build $IMAGE_NAME
    if [[ $IMAGE_NAME == runner ]]; then
        docker build -f utils/build/docker/runner.Dockerfile -t system_tests/runner .

    elif [[ $IMAGE_NAME == agent ]]; then
        docker build \
            -f utils/build/docker/agent.Dockerfile \
            -t system_tests/agent \
            .

    elif [[ $IMAGE_NAME == weblog ]]; then
        DIR=utils/build/docker/${TEST_LIBRARY}.${WEBLOG_VARIANT}
        DOCKERFILE=utils/build/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile

        docker build \
            --progress=plain \
            -f ${DOCKERFILE} \
            -t system_tests/weblog \
            $EXTRA_DOCKER_ARGS \
            .

        # The library version is needed as an env var, and as the runner is executed before the weblog
        # this value need to be present in the image, in order to be inspected. The point here is that
        # ENV command in a Dockerfile can be the result of a command, it must either an hardcoded value
        # or an arg. So we use this 2-step trick to get it.
        # If anybody has an idea to achieve this in a cleanest way ...
        SYSTEM_TESTS_LIBRARY_VERSION=$(docker run system_tests/weblog cat SYSTEM_TESTS_LIBRARY_VERSION)

        docker build \
            --build-arg SYSTEM_TESTS_LIBRARY="$TEST_LIBRARY" \
            --build-arg SYSTEM_TESTS_WEBLOG_VARIANT="$WEBLOG_VARIANT" \
            --build-arg SYSTEM_TESTS_LIBRARY_VERSION="$SYSTEM_TESTS_LIBRARY_VERSION" \
            -f utils/build/docker/set-system-tests-env.Dockerfile \
            -t system_tests/weblog \
            .

    else
        echo "Don't know how to build $IMAGE_NAME"
        exit 1
    fi
done
