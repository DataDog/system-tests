#!/usr/bin/env bash
set -e

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
echo "SCRIPT_DIR: $SCRIPT_DIR"


print_usage() {
    echo -e "${WHITE_BOLD}DESCRIPTION${NC}"
    echo -e "  Builds Docker images for weblog variants with tracers extracted from lib injection init images."
    echo
    echo -e "${WHITE_BOLD}USAGE${NC}"
    echo -e "  ${SCRIPT_NAME} [options...]"
    echo
    echo -e "${WHITE_BOLD}OPTIONS${NC}"
    echo -e "  ${CYAN}--library <lib>${NC}            Language of the tracer (env: TEST_LIBRARY, Mandatory)"
    echo -e "  ${CYAN}--weblog-variant <var>${NC}     Weblog variant (env: WEBLOG_VARIANT). (Mandatory)"
    echo -e "  ${CYAN}--docker-platform <platform>${NC}      Target Docker platform."
    echo -e "  ${CYAN}--lib-init-env <images>${NC}          Origin for the lib init image (dev or prod for latest snapshot and latest release)."  
    echo -e "  ${CYAN}-h, --help${NC}                Display this help message."
    echo -e ""
    echo -e ""
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|java_otel|nodejs|nodejs_otel|php|python|python_otel|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -p|--docker-platform) DOCKER_PLATFORM="--platform $2"; shift ;;
        -e|--lib-init-env) LIB_INIT_ENV="$2"; shift ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1 ;;
    esac
    shift
done

if [[ ! -d "${SCRIPT_DIR}/docker/${TEST_LIBRARY}" ]]; then
    echo "Library ${TEST_LIBRARY} not found or TEST_LIBRARY is not set"
    print_usage
    exit 1
fi

WEBLOG_FOLDER="${SCRIPT_DIR}/docker/${TEST_LIBRARY}/${WEBLOG_VARIANT}"

if [[ (! -f "${WEBLOG_FOLDER}/Dockerfile.lib_init_validator") ]]; then
    echo "Variant [${WEBLOG_VARIANT}] for library [${TEST_LIBRARY}] not found or WEBLOG_VARIANT is not set"
    print_usage
    exit 1
fi

LIB_INIT_ENV="${LIB_INIT_ENV:-prod}"

echo "Building docker init image validator using variant [${WEBLOG_VARIANT}] and library [${TEST_LIBRARY}] for [${LIB_INIT_ENV}] environment"
CURRENT_DIR=$(pwd)
cd $WEBLOG_FOLDER

if test -f "pre_build_lib_init_validator.sh"; then
    sh pre_build_lib_init_validator.sh
fi
docker build --build-arg="LIB_INIT_ENV=${LIB_INIT_ENV}" -t weblog-injection-init:latest -f Dockerfile.lib_init_validator .
cd $CURRENT_DIR