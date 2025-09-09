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
readonly DEFAULT_BUILD_IMAGES=weblog,runner
readonly DEFAULT_DOCKER_MODE=0
readonly DEFAULT_SAVE_TO_BINARIES=0

# Define default weblog variants.
# XXX: Avoid associative arrays for Bash 3 compatibility.
readonly DEFAULT_nodejs=express4
readonly DEFAULT_python=flask-poc
readonly DEFAULT_ruby=rails72
readonly DEFAULT_golang=net-http
readonly DEFAULT_java=spring-boot
readonly DEFAULT_java_otel=spring-boot-native
readonly DEFAULT_python_otel=flask-poc-otel
readonly DEFAULT_nodejs_otel=express4-otel
readonly DEFAULT_php=apache-mod-8.0
readonly DEFAULT_dotnet=poc
readonly DEFAULT_cpp=nginx
readonly DEFAULT_cpp_httpd=httpd
readonly DEFAULT_cpp_nginx=nginx
readonly DEFAULT_python_lambda=apigw-rest
readonly DEFAULT_rust=axum

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
    echo -e "  ${CYAN}--images <images>${NC}          Comma-separated list of images to build (env: BUILD_IMAGES, default: ${DEFAULT_BUILD_IMAGES})."
    echo -e "  ${CYAN}--docker${NC}                   Build docker image instead of local install (env: DOCKER_MODE, default: ${DEFAULT_DOCKER_MODE})."
    echo -e "  ${CYAN}--github-token-file <file>${NC} Path to a file containing a GitHub token used for authenticated operations (e.g. cloning private repos, accessing the API)."
    echo -e "  ${CYAN}--extra-docker-args <args>${NC} Extra arguments passed to docker build (env: EXTRA_DOCKER_ARGS)."
    echo -e "  ${CYAN}--cache-mode <mode>${NC}        Cache mode (env: DOCKER_CACHE_MODE)."
    echo -e "  ${CYAN}--platform <platform>${NC}      Target Docker platform."
    echo -e "  ${CYAN}--list-libraries${NC}           Lists all available libraries and exits."
    echo -e "  ${CYAN}--list-weblogs${NC}             Lists all available weblogs for a library and exits."
    echo -e "  ${CYAN}--default-weblog${NC}           Prints the name of the default weblog for a given library and exits."
    echo -e "  ${CYAN}--binary-path${NC}              Optional. Path of a directory binaries will be copied from. Should be used for local development only."
    echo -e "  ${CYAN}--binary-url${NC}               Optional. Url of the client library redistributable. Should be used for local development only."
    echo -e "  ${CYAN}--save-to-binaries${NC}         Optional. Save image in binaries folder as a tar.gz file."
    echo -e "  ${CYAN}--help${NC}                     Prints this message and exits."
    echo
    echo -e "${WHITE_BOLD}EXAMPLES${NC}"
    echo -e "  Build default images:"
    echo -e "    ${SCRIPT_NAME}"
    echo -e "  Build images for Java and Spring Boot:"
    echo -e "    ${SCRIPT_NAME} --library java --weblog-variant spring-boot"
    echo -e "  Build default images for .NET with binary path:"
    echo -e "    ${SCRIPT_NAME} dotnet --binary-path "/mnt/c/dev/dd-trace-dotnet-linux/tmp/linux-x64""
    echo -e "  Build default images for .NET with binary url:"
    echo -e "    ${SCRIPT_NAME} ./build.sh dotnet --binary-url "https://github.com/DataDog/dd-trace-dotnet/releases/download/v2.27.0/datadog-dotnet-apm-2.27.0.tar.gz""
    echo -e "  List libraries:"
    echo -e "    ${SCRIPT_NAME} --list-libraries"
    echo -e "  List weblogs for PHP:"
    echo -e "    ${SCRIPT_NAME} --list-weblogs --library php"
    echo -e "  Print default weblog for Python:"
    echo -e "    ${SCRIPT_NAME} --default-weblog --library python"
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
    # In CI environments we don't have a docker daemon to load the resulting image.
    # Unless DOCKER_HOST is set, then we're running on a Docker in Docker runner.
    if [[ -z "${CI:-}" ]] || [[ -n "${CI:-}" && -n "$DOCKER_HOST" ]]; then
        EXTRA_DOCKER_ARGS+=("--load")
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
                    if command -v python3.12 &> /dev/null
                    then
                        python3.12 -m venv venv --copies
                    elif command -v python3.9 &> /dev/null
                    then
                        echo "⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️"
                        echo "DEPRECRATION WARNING: you are using python3.9 to run system-tests."
                        echo "This won't be supported soon. Install python 3.12, then run:"
                        echo "> rm -rf venv && ./build.sh -i runner"
                        echo "⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️"
                        python3.9 -m venv venv
                    else
                        echo "Can't find python3.12, please install it"
                    fi
                fi
                source venv/bin/activate
                python -m pip install --upgrade pip setuptools==75.8.0
            fi
            python -m pip install -e .
            cp requirements.txt venv/requirements.txt


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
            echo "Building agent is not needed anymore, system-tests now use directly the agent image from docker hub."

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

            # keep this name consistent with WeblogContainer.get_image_list()
            BINARIES_FILENAME=binaries/${TEST_LIBRARY}-${WEBLOG_VARIANT}-weblog.tar.gz

            if [ -f $BINARIES_FILENAME ]; then
                echo "Loading image from $BINARIES_FILENAME"
                docker load --input $BINARIES_FILENAME
            else

                # dd-trace-py compilation if required
                if [[ $TEST_LIBRARY == python ]] && [[ -d "binaries/dd-trace-py" ]]; then
                    echo "Compiling dd-trace-py"

                    # Choose Python version based on weblog variant
                    case "$WEBLOG_VARIANT" in
                        flask-poc|django-poc|fastapi|uds-flask|uwsgi-poc)
                            PYTHON_VERSION="3.11"
                            ;;
                        django-py3.13)
                            PYTHON_VERSION="3.13"
                            ;;
                        python3.12)
                            PYTHON_VERSION="3.12"
                            ;;
                        *)
                            echo "Error: Unknown weblog variant, python version could not be determined" >&2
                            exit 1
                            ;;
                    esac

                    echo "Using Python version: $PYTHON_VERSION"
                    docker run -v ./binaries/:/app -w /app ghcr.io/datadog/dd-trace-py/testrunner bash -c "pyenv global $PYTHON_VERSION; pip wheel --no-deps -w . /app/dd-trace-py"
                fi

                DOCKERFILE=utils/build/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile

                GITHUB_TOKEN_SECRET_ARG=""

                if [ -n "${GITHUB_TOKEN_FILE:-}" ]; then
                    if [ ! -f "$GITHUB_TOKEN_FILE" ]; then
                        echo "Error: GitHub token file not found at $GITHUB_TOKEN_FILE" >&2
                        exit 1
                    fi

                    echo "Using GitHub token from $GITHUB_TOKEN_FILE"
                    GITHUB_TOKEN_SECRET_ARG="--secret id=github_token,src=$GITHUB_TOKEN_FILE"
                fi

                docker buildx build \
                    --build-arg BUILDKIT_INLINE_CACHE=1 \
                    --load \
                    --progress=plain \
                    ${DOCKER_PLATFORM_ARGS} \
                    ${GITHUB_TOKEN_SECRET_ARG} \
                    -f ${DOCKERFILE} \
                    --label "system-tests-library=${TEST_LIBRARY}" \
                    --label "system-tests-weblog-variant=${WEBLOG_VARIANT}" \
                    -t system_tests/weblog \
                    $CACHE_TO \
                    $CACHE_FROM \
                    $EXTRA_DOCKER_ARGS \
                    .

                if test -f "binaries/waf_rule_set.json"; then

                    docker buildx build \
                        --build-arg BUILDKIT_INLINE_CACHE=1 \
                        --load \
                        --progress=plain \
                        ${DOCKER_PLATFORM_ARGS} \
                        -f utils/build/docker/overwrite_waf_rules.Dockerfile \
                        -t system_tests/weblog \
                        $EXTRA_DOCKER_ARGS \
                        .
                fi

                if [[ $SAVE_TO_BINARIES == 1 ]]; then
                    echo "Saving image to $BINARIES_FILENAME"
                    docker save system_tests/weblog | gzip > $BINARIES_FILENAME
                fi
            fi
        elif [[ $IMAGE_NAME == lambda-proxy ]]; then
            ./utils/build/build_lambda_proxy.sh "${EXTRA_DOCKER_ARGS[@]}"
        else
            echo "Don't know how to build $IMAGE_NAME"
            exit 1
        fi
    done
}

# Main
COMMAND=build

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp_nginx|cpp_httpd|dotnet|golang|java|java_otel|nodejs|nodejs_otel|php|python|python_lambda|python_otel|ruby|rust) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -i|--images) BUILD_IMAGES="$2"; shift ;;
        -d|--docker) DOCKER_MODE=1;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -e|--extra-docker-args) EXTRA_DOCKER_ARGS="$2"; shift ;;
        -c|--cache-mode) DOCKER_CACHE_MODE="$2"; shift ;;
        -p|--docker-platform) DOCKER_PLATFORM="--platform $2"; shift ;;
        -s|--save-to-binaries) SAVE_TO_BINARIES=1 ;;
        --github-token-file) GITHUB_TOKEN_FILE="$2"; shift ;;
        --binary-url) BINARY_URL="$2"; shift ;;
        --binary-path) BINARY_PATH="$2"; shift ;;
        --list-libraries) COMMAND=list-libraries ;;
        --list-weblogs) COMMAND=list-weblogs ;;
        --default-weblog) COMMAND=default-weblog ;;
        -h|--help) print_usage; exit 0 ;;
        --agent-base-image) AGENT_BASE_IMAGE="$2"; shift ;;  # deprecated
        *) echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1 ;;
    esac
    shift
done

# Set defaults
DOCKER_CACHE_MODE="${DOCKER_CACHE_MODE:-}"
EXTRA_DOCKER_ARGS="${EXTRA_DOCKER_ARGS:-}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"
DOCKER_MODE="${DOCKER_MODE:-${DEFAULT_DOCKER_MODE}}"
SAVE_TO_BINARIES="${SAVE_TO_BINARIES:-${DEFAULT_SAVE_TO_BINARIES}}"
BUILD_IMAGES="${BUILD_IMAGES:-${DEFAULT_BUILD_IMAGES}}"
TEST_LIBRARY="${TEST_LIBRARY:-${DEFAULT_TEST_LIBRARY}}"
BINARY_PATH="${BINARY_PATH:-}"
BINARY_URL="${BINARY_URL:-}"
GITHUB_TOKEN_FILE="${GITHUB_TOKEN_FILE:-}"

if [[ "${BUILD_IMAGES}" =~ /weblog/ && ! -d "${SCRIPT_DIR}/docker/${TEST_LIBRARY}" ]]; then
    echo "Library ${TEST_LIBRARY} not found"
    echo "Available libraries: $(echo $(list-libraries))"
    exit 1
fi

WEBLOG_VARIANT="${WEBLOG_VARIANT:-$(default-weblog)}"

if [[ "${BUILD_IMAGES}" =~ /weblog/ && (-n "$WEBLOG_VARIANT") && (! -f "${SCRIPT_DIR}/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile") ]]; then
    echo "Variant ${WEBLOG_VARIANT} for library ${TEST_LIBRARY} not found"
    echo "Available weblog variants for ${TEST_LIBRARY}: $(echo $(list-weblogs))"
    exit 1
fi

"${COMMAND}"
