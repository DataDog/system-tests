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

DOCKER_REGISTRY_CACHE_PATH="${DOCKER_REGISTRY_CACHE_PATH:-ghcr.io/datadog/system-tests}"
ALIAS_CACHE_FROM="R" #read cache
ALIAS_CACHE_TO="W" #write cache

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|nodejs|php|python|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -i|--images) BUILD_IMAGES="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -e|--extra-docker-args) EXTRA_DOCKER_ARGS="$2"; shift ;;
        -c|--cache-mode) DOCKER_CACHE_MODE="$2"; shift ;;
        -p|--docker-platform) DOCKER_PLATFORM="--platform $2"; shift ;;
        *) cat utils/build/README.md; exit 1 ;;
    esac
    shift
done

# default: build all images
BUILD_IMAGES=${BUILD_IMAGES:-weblog,runner,agent}

# default: node
TEST_LIBRARY=${TEST_LIBRARY:-nodejs}

if [ "$TEST_LIBRARY" = "nodejs" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-express4}

elif [ "$TEST_LIBRARY" = "python" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-flask-poc}

elif [ "$TEST_LIBRARY" = "ruby" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-rails70}

elif [ "$TEST_LIBRARY" = "golang" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-net-http}

elif [ "$TEST_LIBRARY" = "java" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-spring-boot}

elif [ "$TEST_LIBRARY" = "php" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-apache-mod-8.0}

elif [ "$TEST_LIBRARY" = "dotnet" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-poc}

elif [ "$TEST_LIBRARY" = "cpp" ]; then
    WEBLOG_VARIANT=${WEBLOG_VARIANT:-nginx}

else
    echo "Unknown library: ${TEST_LIBRARY}"
    cat utils/build/README.md
    exit 1
fi

if [[ "$DOCKER_CACHE_MODE" == *"$ALIAS_CACHE_FROM"* ]]; then
  echo "Setting remote cache for read"
  CACHE_FROM="--cache-from type=registry,ref=${DOCKER_REGISTRY_CACHE_PATH}/${WEBLOG_VARIANT}:cache"
fi
if [[ "$DOCKER_CACHE_MODE" == *"$ALIAS_CACHE_TO"* ]]; then
  echo "Setting remote cache for write"
  CACHE_TO="--cache-to type=registry,ref=${DOCKER_REGISTRY_CACHE_PATH}/${WEBLOG_VARIANT}:cache"
fi

echo "=================================="
echo "build images for system tests"
echo ""
echo "TEST_LIBRARY:      $TEST_LIBRARY"
echo "WEBLOG_VARIANT:    $WEBLOG_VARIANT"
echo "BUILD_IMAGES:      $BUILD_IMAGES"
echo "EXTRA_DOCKER_ARGS: $EXTRA_DOCKER_ARGS"
echo ""

#Issues with Mac M1 arm64 arch. This patch is intended to affect Mac M1 only.
ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
DOCKER_PLATFORM_ARGS="${DOCKER_PLATFORM:-"--platform linux/amd64"}" 

if [ "$ARCH" = "arm64" ]; then
    DOCKER_PLATFORM_ARGS="${DOCKER_PLATFORM:-"--platform linux/arm64/v8"}" 
fi

# Build images
for IMAGE_NAME in $(echo $BUILD_IMAGES | sed "s/,/ /g")
do

    echo "-----------------------"
    echo Build $IMAGE_NAME
    if [[ $IMAGE_NAME == runner ]]; then
        docker build -f utils/build/docker/runner.Dockerfile -t system_tests/runner $EXTRA_DOCKER_ARGS .

    elif [[ $IMAGE_NAME == agent ]]; then
        if [ -f ./binaries/agent-image ]; then
            AGENT_BASE_IMAGE=$(cat ./binaries/agent-image)            
        else
            AGENT_BASE_IMAGE="datadog/agent"
        fi

        echo "using $AGENT_BASE_IMAGE image for datadog agent"

        docker build \
            --progress=plain \
            -f utils/build/docker/agent.Dockerfile \
            -t system_tests/agent \
            --build-arg AGENT_IMAGE="$AGENT_BASE_IMAGE" \
            $EXTRA_DOCKER_ARGS \
            .

        SYSTEM_TESTS_AGENT_VERSION=$(docker run --rm system_tests/agent /opt/datadog-agent/bin/agent/agent version)

        docker build \
            --build-arg SYSTEM_TESTS_AGENT_VERSION="$SYSTEM_TESTS_AGENT_VERSION" \
            -f utils/build/docker/set-system-tests-agent-env.Dockerfile \
            -t system_tests/agent \
            .

    elif [[ $IMAGE_NAME == weblog ]]; then
        DOCKERFILE=utils/build/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile

        if [ $ATTEMPT -gt 1 ]
        then
            echo "Disabling remote cache reading"
            CACHE_FROM="--build-arg CACHEBUST=$(date +%s)"
        fi
        echo "CACHE VALUE:::::>>>>> $CACHE_FROM"
        echo "DOCKER_PLATFORM_ARGS: $DOCKER_PLATFORM_ARGS"
        echo "CACHE TO :::::>>>>> $CACHE_TO"
         echo "EXTRA_DOCKER_ARGS TO :::::>>>>> $EXTRA_DOCKER_ARGS"
        docker buildx build \
            --progress=plain \
            ${DOCKER_PLATFORM_ARGS} \
            -f ${DOCKERFILE} \
            -t system_tests/weblog \
            $CACHE_TO \
            $CACHE_FROM \
            $EXTRA_DOCKER_ARGS \
            --load \
            .

        if test -f "binaries/waf_rule_set.json"; then
            SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION=$(cat binaries/waf_rule_set.json | jq -r '.metadata.rules_version // "1.2.5"')

            docker build \
                --progress=plain \
                ${DOCKER_PLATFORM_ARGS} \
                --build-arg SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION="$SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION" \
                -f utils/build/docker/overwrite_waf_rules.Dockerfile \
                -t system_tests/weblog \
                $EXTRA_DOCKER_ARGS \
                .
        fi

        # The library version is needed as an env var, and as the runner is executed before the weblog
        # this value need to be present in the image, in order to be inspected. The point here is that
        # ENV command in a Dockerfile can be the result of a command, it must either an hardcoded value
        # or an arg. So we use this 2-step trick to get it.
        # If anybody has an idea to achieve this in a cleanest way ...

        echo "Getting system test context and saving it in weblog image"
        SYSTEM_TESTS_LIBRARY_VERSION=$(docker run --rm system_tests/weblog cat SYSTEM_TESTS_LIBRARY_VERSION)
        SYSTEM_TESTS_PHP_APPSEC_VERSION=$(docker run --rm system_tests/weblog bash -c "touch SYSTEM_TESTS_PHP_APPSEC_VERSION && cat SYSTEM_TESTS_PHP_APPSEC_VERSION")
        SYSTEM_TESTS_LIBDDWAF_VERSION=$(docker run --rm system_tests/weblog cat SYSTEM_TESTS_LIBDDWAF_VERSION)
        SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION=$(docker run --rm system_tests/weblog cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION) 

        docker build \
            --progress=plain \
            ${DOCKER_PLATFORM_ARGS} \
            --build-arg SYSTEM_TESTS_LIBRARY="$TEST_LIBRARY" \
            --build-arg SYSTEM_TESTS_WEBLOG_VARIANT="$WEBLOG_VARIANT" \
            --build-arg SYSTEM_TESTS_LIBRARY_VERSION="$SYSTEM_TESTS_LIBRARY_VERSION" \
            --build-arg SYSTEM_TESTS_PHP_APPSEC_VERSION="$SYSTEM_TESTS_PHP_APPSEC_VERSION" \
            --build-arg SYSTEM_TESTS_LIBDDWAF_VERSION="$SYSTEM_TESTS_LIBDDWAF_VERSION" \
            --build-arg SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION="$SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION" \
            -f utils/build/docker/set-system-tests-weblog-env.Dockerfile \
            -t system_tests/weblog \
            .

    else
        echo "Don't know how to build $IMAGE_NAME"
        exit 1
    fi
done

