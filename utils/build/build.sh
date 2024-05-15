#!/usr/bin/env bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

# set .env if exists. Allow users to keep their conf via env vars
if [[ -f "./.env" ]]; then
    source ./.env
fi

WEBLOG_VARIANT=${WEBLOG_VARIANT:-${HTTP_FRAMEWORK:-}}

readonly DOCKER_REGISTRY_CACHE_PATH="${DOCKER_REGISTRY_CACHE_PATH:-ghcr.io/datadog/system-tests}"
readonly ALIAS_CACHE_FROM="R" #read cache
readonly ALIAS_CACHE_TO="W" #write cache

readonly DEFAULT_TEST_LIBRARY=nodejs
readonly DEFAULT_BUILD_IMAGES=weblog,runner,agent
readonly DEFAULT_DOCKER_MODE=0

# Define default weblog variants.
# XXX: Avoid associative arrays for Bash 3 compatibility.
readonly DEFAULT_nodejs=express4
readonly DEFAULT_python=flask-poc
readonly DEFAULT_ruby=rails70
readonly DEFAULT_golang=net-http
readonly DEFAULT_java=spring-boot
readonly DEFAULT_java_otel=spring-boot-native
readonly DEFAULT_python_otel=flask-poc-otel
readonly DEFAULT_nodejs_otel=express4-otel
readonly DEFAULT_php=apache-mod-8.0
readonly DEFAULT_dotnet=poc
readonly DEFAULT_cpp=nginx

readonly SCRIPT_NAME="${0}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

readonly CYAN='\033[0;36m'
readonly NC='\033[0m'
readonly WHITE_BOLD='\033[1;37m'

print_usage() {
    echo -e "${WHITE_BOLD}DESCRIPTION${NC}"
    echo -e "  Builds Docker images for weblog variants with tracers."
    echo
    echo -e "${WHITE_BOLD}USAGE${NC}"
    echo -e "  ${SCRIPT_NAME} [options...]"
    echo
    echo -e "${WHITE_BOLD}OPTIONS${NC}"
    echo -e "  ${CYAN}--library <lib>${NC}            Language of the tracer (env: TEST_LIBRARY, default: ${DEFAULT_TEST_LIBRARY})."
    echo -e "  ${CYAN}--weblog-variant <var>${NC}     Weblog variant (env: WEBLOG_VARIANT)."
    echo -e "  ${CYAN}--lib-injection-group <var>${NC}       You can choose: 'k8s','lib-init' or 'host-injection' to work with lib injection group of weblogs different from the default system-tests."
    echo -e "  ${CYAN}--images <images>${NC}          Comma-separated list of images to build (env: BUILD_IMAGES, default: ${DEFAULT_BUILD_IMAGES})."
    echo -e "  ${CYAN}--docker${NC}                   Build docker image instead of local install (env: DOCKER_MODE, default: ${DEFAULT_DOCKER_MODE})."
    echo -e "  ${CYAN}--extra-docker-args <args>${NC} Extra arguments passed to docker build (env: EXTRA_DOCKER_ARGS)."
    echo -e "  ${CYAN}--cache-mode <mode>${NC}        Cache mode (env: DOCKER_CACHE_MODE)."
    echo -e "  ${CYAN}--platform <platform>${NC}      Target Docker platform."
    echo -e "  ${CYAN}--list-libraries${NC}           Lists all available libraries and exits."
    echo -e "  ${CYAN}--list-weblogs${NC}             Lists all available weblogs for a library and exits."
    echo -e "  ${CYAN}--default-weblog${NC}           Prints the name of the default weblog for a given library and exits."
    echo -e "  ${CYAN}--binary-path${NC}              Optional. Path of a directory binaries will be copied from. Should be used for local development only."
    echo -e "  ${CYAN}--binary-url${NC}               Optional. Url of the client library redistributable. Should be used for local development only."
    echo -e "  ${CYAN}--help${NC}                     Prints this message and exits."
    echo
    echo -e "${WHITE_BOLD}EXAMPLES${NC}"
    echo -e "  Build default images:"
    echo -e "    ${SCRIPT_NAME}"
    echo -e "  Build images for Java and Spring Boot:"
    echo -e "    ${SCRIPT_NAME} --library java --weblog-variant spring-boot"
    echo -e "  Build default images for Dotnet with binary path:"
    echo -e "    ${SCRIPT_NAME} dotnet --binary-path "/mnt/c/dev/dd-trace-dotnet-linux/tmp/linux-x64""    
    echo -e "  Build default images for Dotnet with binary url:"
    echo -e "    ${SCRIPT_NAME} ./build.sh dotnet --binary-url "https://github.com/DataDog/dd-trace-dotnet/releases/download/v2.27.0/datadog-dotnet-apm-2.27.0.tar.gz""
    echo -e "  Build a weblog from 'host-injection' group:"
    echo -e "    ${SCRIPT_NAME} --weblog-variant sample-app.amazonLinux2 --lib-injection-group host-injection"
    echo -e "  List libraries:"
    echo -e "    ${SCRIPT_NAME} --list-libraries"
    echo -e "  List weblogs for PHP:"
    echo -e "    ${SCRIPT_NAME} --list-weblogs --library php"
    echo -e "  Print default weblog for Python:"
    echo -e "    ${SCRIPT_NAME} --default-weblogs --library python"
    echo
    echo -e "More info at https://github.com/DataDog/system-tests/blob/main/docs/execute/build.md"
    echo
}

list-libraries() {
    find "${SCRIPT_DIR}/docker" -mindepth 1 -maxdepth 1 -type d | sed -e 's~.*/~~g'
}

list-weblogs() {
    find "${SCRIPT_DIR}/docker/${TEST_LIBRARY}" -maxdepth 1 -name '*.Dockerfile' -type f | sed -e 's~.*/~~g' -e 's~.Dockerfile$~~g'
}

default-weblog() {
    local var="DEFAULT_${TEST_LIBRARY}"
    echo -n "${!var}"
}

build() {
    CACHE_TO=
    CACHE_FROM=
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

    # Issues with Mac M1 arm64 arch. This patch is intended to affect Mac M1 only.
    ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')

    case $ARCH in
    arm64|aarch64) DOCKER_PLATFORM_ARGS="${DOCKER_PLATFORM:-"--platform linux/arm64/v8"}";;
    *)             DOCKER_PLATFORM_ARGS="${DOCKER_PLATFORM:-"--platform linux/amd64"}";;
    esac

    if [ -n $LIB_INJECTION_GROUP ]; then
        build_with_lib_injection_group
        exit 0
    fi

    # Build images
    for IMAGE_NAME in $(echo $BUILD_IMAGES | sed "s/,/ /g")
    do

        echo "-----------------------"
        echo Build $IMAGE_NAME
        if [[ $IMAGE_NAME == runner ]] && [[ $DOCKER_MODE != 1 ]]; then
            if [[ -z "${IN_NIX_SHELL:-}" ]]; then
              if [ ! -d "venv/" ]
              then
                  echo "Build virtual env"
                  python3.9 -m venv venv
              fi

              source venv/bin/activate
              python -m pip install --upgrade pip
            fi
            pip install -r requirements.txt

        elif [[ $IMAGE_NAME == runner ]] && [[ $DOCKER_MODE == 1 ]]; then
            docker buildx build \
                --build-arg BUILDKIT_INLINE_CACHE=1 \
                --load \
                --progress=plain \
                -f utils/build/docker/runner.Dockerfile \
                -t system_tests/runner \
                $EXTRA_DOCKER_ARGS \
                .

        elif [[ $IMAGE_NAME == proxy ]]; then
            docker buildx build \
                --build-arg BUILDKIT_INLINE_CACHE=1 \
                --load \
                --progress=plain \
                -f utils/build/docker/proxy.Dockerfile \
                -t datadog/system-tests:proxy-v1 \
                $EXTRA_DOCKER_ARGS \
                .

        elif [[ $IMAGE_NAME == agent ]]; then
            if [ -f ./binaries/agent-image ]; then
                AGENT_BASE_IMAGE=$(cat ./binaries/agent-image)
            else
                AGENT_BASE_IMAGE="datadog/agent"
            fi

            echo "using $AGENT_BASE_IMAGE image for datadog agent"

            docker buildx build \
                --build-arg BUILDKIT_INLINE_CACHE=1 \
                --load \
                --progress=plain \
                -f utils/build/docker/agent.Dockerfile \
                -t system_tests/agent \
		--pull \
                --build-arg AGENT_IMAGE="$AGENT_BASE_IMAGE" \
                $EXTRA_DOCKER_ARGS \
                .

        elif [[ $IMAGE_NAME == weblog ]]; then
            clean-binaries() {
                find . -mindepth 1 -type d -exec rm -rf {} +
                find . ! -name 'README.md' -type f -exec rm -f {} +
            }

            if ! [[ -z "$BINARY_URL" ]]; then 
                cd binaries
                clean-binaries
                curl -L -O $BINARY_URL
                cd ..
            fi

            if ! [[ -z "$BINARY_PATH" ]]; then 
                cd binaries
                clean-binaries
                cp -r $BINARY_PATH/* ./
                cd ..
            fi

            DOCKERFILE=utils/build/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile          

            docker buildx build \
                --build-arg BUILDKIT_INLINE_CACHE=1 \
                --load \
                --progress=plain \
                ${DOCKER_PLATFORM_ARGS} \
                -f ${DOCKERFILE} \
                -t system_tests/weblog \
                $CACHE_TO \
                $CACHE_FROM \
                $EXTRA_DOCKER_ARGS \
                .

            if test -f "binaries/waf_rule_set.json"; then
                SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION=$(cat binaries/waf_rule_set.json | jq -r '.metadata.rules_version // "1.2.5"')

                docker buildx build \
                    --build-arg BUILDKIT_INLINE_CACHE=1 \
                    --load \
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
            SYSTEM_TESTS_LIBRARY_VERSION=$(docker run ${DOCKER_PLATFORM_ARGS} --rm system_tests/weblog cat SYSTEM_TESTS_LIBRARY_VERSION)
            SYSTEM_TESTS_LIBDDWAF_VERSION=$(docker run ${DOCKER_PLATFORM_ARGS} --rm system_tests/weblog cat SYSTEM_TESTS_LIBDDWAF_VERSION)
            SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION=$(docker run ${DOCKER_PLATFORM_ARGS} --rm system_tests/weblog cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)

            docker buildx build \
                --build-arg BUILDKIT_INLINE_CACHE=1 \
                --load \
                --progress=plain \
                ${DOCKER_PLATFORM_ARGS} \
                --build-arg SYSTEM_TESTS_LIBRARY="$TEST_LIBRARY" \
                --build-arg SYSTEM_TESTS_WEBLOG_VARIANT="$WEBLOG_VARIANT" \
                --build-arg SYSTEM_TESTS_LIBRARY_VERSION="$SYSTEM_TESTS_LIBRARY_VERSION" \
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
}

build_with_lib_injection_group() {
    WEBLOG_VARIANT_PATH="${SCRIPT_DIR}/ssi/${TEST_LIBRARY}/${WEBLOG_VARIANT}/Dockerfile${WEBLOG_VARIANT_SUFIX}.${LIB_INJECTION_GROUP}"
    echo "LIB_INJECTION_GROUP: $LIB_INJECTION_GROUP"
    LIB_ENV=${ENV:-"prod"}
    echo "ENV: $LIB_ENV"
    echo "-----------------------"
    echo Build $WEBLOG_VARIANT_PATH
    if [[ $LIB_INJECTION_GROUP == "k8s" ]]; then
        build_k8s_lib_injection_group
    else

        docker buildx build  --build-arg="LIB_INIT_ENV=${LIB_ENV}" -t weblog-injection-host:latest -f "${WEBLOG_VARIANT_PATH}" --load .
    fi
}
build_k8s_lib_injection_group() {
        #Validate the K8s environment before building the image
        #Validate k8s: Check if DOCKER_REGISTRY_IMAGES_PATH is set
        echo "Building image for k8s lib injection group"
        if [ -z ${DOCKER_REGISTRY_IMAGES_PATH+x} ]; then
            echo "You must provide a docker registry path"
            echo "Example 1: export DOCKER_REGISTRY_IMAGES_PATH=docker.io/MY_DOCKERHUB_USERNAME"
            echo "Example 2: export DOCKER_REGISTRY_IMAGES_PATH=ghcr.io/datadog"
            exit 1
        fi
        #Validate k8s: You must be logged to a docker registry/ghcr registry
        docker login $DOCKER_REGISTRY_IMAGES_PATH
        
        #Validate K8s: check env. DOCKER_IMAGE_TAG is the tag for the lib init image
        if [ ${ENV:-"prod"} == "prod" ]; then
            export DOCKER_IMAGE_TAG="latest"
        elif [ $ENV == "dev" ]; then
            export DOCKER_IMAGE_TAG="latest_snapshot"
        else
            echo "Setting DOCKER_IMAGE_TAG to local"
            export DOCKER_IMAGE_TAG="local"
        fi

        #Validate K8s: check if DOCKER_IMAGE_WEBLOG_TAG is set
        if [ -z ${DOCKER_IMAGE_WEBLOG_TAG+x} ]; then
            echo "Working with image weblog tag: latest"
            export DOCKER_IMAGE_WEBLOG_TAG="latest"
        fi

        #Build weblog full tag
        if [ $DOCKER_REGISTRY_IMAGES_PATH == ghcr.* ]; then
            FULL_WEBLOG_PUSH_TAG="$DOCKER_REGISTRY_IMAGES_PATH/system-tests/${WEBLOG_VARIANT}:${DOCKER_IMAGE_WEBLOG_TAG}"
        else
            FULL_WEBLOG_PUSH_TAG="$DOCKER_REGISTRY_IMAGES_PATH/${WEBLOG_VARIANT}:${DOCKER_IMAGE_WEBLOG_TAG}"
        fi
        #Print the environment
        echo "ENV: $LIB_ENV"
        echo "DOCKER_REGISTRY_IMAGES_PATH: $DOCKER_REGISTRY_IMAGES_PATH"
        echo "DOCKER_IMAGE_WEBLOG_TAG: $DOCKER_IMAGE_WEBLOG_TAG"
        echo "DOCKER_IMAGE_TAG: $DOCKER_IMAGE_TAG"
        echo "FULL_WEBLOG_PUSH_TAG: $FULL_WEBLOG_PUSH_TAG"
        echo "-----------------------"
        #Build and push the image
        docker buildx build -t "${FULL_WEBLOG_PUSH_TAG}" -f "${WEBLOG_VARIANT_PATH}" --push .
}

validate_lib_injection_group_data() {
    if [ "$LIB_INJECTION_GROUP" != "k8s" ] && [ "$LIB_INJECTION_GROUP" != "lib-init" ] && [ "$LIB_INJECTION_GROUP" != "host-injection" ]; then
        echo "Invalid weblog group. You should choose: 'k8s','lib-init' or 'host-injection'"
        exit 1
    fi
    if [ -z $WEBLOG_VARIANT ]; then
        echo "You must provide a weblog variant"
        exit 1
    fi
    #Used specifically for host-injection group to set the machine that we are going to use
    WEBLOG_VARIANT_SUFIX=$(echo "${WEBLOG_VARIANT}"|grep -o "\..*$")||true
    WEBLOG_VARIANT="${WEBLOG_VARIANT%%.*}"
    echo "WEBLOG_VARIANT: $WEBLOG_VARIANT"
    echo "WEBLOG_VARIANT_SUFIX: $WEBLOG_VARIANT_SUFIX"
    echo "----> ${SCRIPT_DIR}/ssi/${TEST_LIBRARY}/${WEBLOG_VARIANT}/Dockerfile${WEBLOG_VARIANT_SUFIX}.${LIB_INJECTION_GROUP}" 
    #Check if variant exists on this group
    if [ ! -f "${SCRIPT_DIR}/ssi/${TEST_LIBRARY}/${WEBLOG_VARIANT}/Dockerfile${WEBLOG_VARIANT_SUFIX}.${LIB_INJECTION_GROUP}" ]; then
        echo "Variant [${WEBLOG_VARIANT}] for group [${LIB_INJECTION_GROUP}] not found"
        exit 1
    fi
}

# Main
COMMAND=build

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|java_otel|nodejs|nodejs_otel|php|python|python_otel|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -i|--images) BUILD_IMAGES="$2"; shift ;;
        -d|--docker) DOCKER_MODE=1;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -lg|--lib-injection-group) LIB_INJECTION_GROUP="$2"; shift ;;
        -e|--extra-docker-args) EXTRA_DOCKER_ARGS="$2"; shift ;;
        -c|--cache-mode) DOCKER_CACHE_MODE="$2"; shift ;;
        -p|--docker-platform) DOCKER_PLATFORM="--platform $2"; shift ;;
        --binary-url) BINARY_URL="$2"; shift ;;
        --binary-path) BINARY_PATH="$2"; shift ;;
        --list-libraries) COMMAND=list-libraries ;;
        --list-weblogs) COMMAND=list-weblogs ;;
        --default-weblog) COMMAND=default-weblog ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1 ;;
    esac
    shift
done

# Set defaults
DOCKER_CACHE_MODE="${DOCKER_CACHE_MODE:-}"
EXTRA_DOCKER_ARGS="${EXTRA_DOCKER_ARGS:-}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"
DOCKER_MODE="${DOCKER_MODE:-${DEFAULT_DOCKER_MODE}}"
BUILD_IMAGES="${BUILD_IMAGES:-${DEFAULT_BUILD_IMAGES}}"
TEST_LIBRARY="${TEST_LIBRARY:-${DEFAULT_TEST_LIBRARY}}"
BINARY_PATH="${BINARY_PATH:-}"
BINARY_URL="${BINARY_URL:-}"

if [[ "${BUILD_IMAGES}" =~ /weblog/ && ! -d "${SCRIPT_DIR}/docker/${TEST_LIBRARY}" ]]; then
    echo "Library ${TEST_LIBRARY} not found"
    echo "Available libraries: $(echo $(list-libraries))"
    exit 1
fi

# Check if we are working with a different group of weblogs different from the default system-tests
if [ -n ${LIB_INJECTION_GROUP+x} ]; then
    validate_lib_injection_group_data
else
    #Default system-tests build
    WEBLOG_VARIANT="${WEBLOG_VARIANT:-$(default-weblog)}"
    if [[ "${BUILD_IMAGES}" =~ /weblog/ && (-n "$WEBLOG_VARIANT") && (! -f "${SCRIPT_DIR}/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile") ]]; then
        echo "Variant ${WEBLOG_VARIANT} for library ${TEST_LIBRARY} not found"
        echo "Available weblog variants for ${TEST_LIBRARY}: $(echo $(list-weblogs))"
        exit 1
    fi
fi
"${COMMAND}"
