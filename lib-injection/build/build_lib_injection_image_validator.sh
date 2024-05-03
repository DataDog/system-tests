#!/usr/bin/env bash
set -e

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
echo "SCRIPT_DIR: $SCRIPT_DIR"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|java_otel|nodejs|nodejs_otel|php|python|python_otel|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -p|--docker-platform) DOCKER_PLATFORM="--platform $2"; shift ;;
        -e|--lib-init-env) LIB_INIT_ENV="$2"; shift ;;
        *) echo "Invalid argument: ${1:-}"; echo; exit 1 ;;
    esac
    shift
done

if [[ ! -d "${SCRIPT_DIR}/docker/${TEST_LIBRARY}" ]]; then
    echo "Library ${TEST_LIBRARY} not found or TEST_LIBRARY is not set"
    exit 1
fi

WEBLOG_FOLDER="${SCRIPT_DIR}/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}"

if [[ (! -f "${WEBLOG_FOLDER}/Dockerfile.lib_init_validator") ]]; then
    echo "Variant [${WEBLOG_VARIANT}] for library [${TEST_LIBRARY}] not found or WEBLOG_VARIANT is not set"
    exit 1
fi

LIB_INIT_ENV="${LIB_INIT_ENV:-prod}"

echo "Building docker init image validator using variant [${WEBLOG_VARIANT}] and library [${TEST_LIBRARY}] for [${LIB_INIT_ENV}] environment"
CURRENT_DIR=$(pwd)
cd $WEBLOG_FOLDER
docker build --build-arg="LIB_INIT_ENV=${LIB_INIT_ENV}" -t weblog-injection-init:latest -f Dockerfile.lib_init_validator .
cd $CURRENT_DIR