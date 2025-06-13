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
    echo -e "  ${CYAN}--push-tag <var>${NC}     The image will be pushed to docker registry (env: PUSH_TAG)."
    echo -e "  ${CYAN}--docker-platform <platform>${NC}      Target Docker platform."
    echo -e "  ${CYAN}-h, --help${NC}                Display this help message."
    echo -e ""
    echo -e ""
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|java_otel|nodejs|nodejs_otel|php|python|python_otel|ruby|rust) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -dp|--docker-platform) DOCKER_PLATFORM="--platform $2"; shift ;;
        -pt|--push-tag) PUSH_TAG="$2"; shift ;;
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

if [[ (! -f "${WEBLOG_FOLDER}/Dockerfile") ]]; then
    echo "Variant [${WEBLOG_VARIANT}] for library [${TEST_LIBRARY}] not found or WEBLOG_VARIANT is not set"
    print_usage
    exit 1
fi

if [[ $TEST_LIBRARY == "ruby" ]]; then
    cp -r $WEBLOG_FOLDER/../lib_injection_rails_app $WEBLOG_FOLDER/lib_injection_rails_app
    cp $WEBLOG_FOLDER/../.dockerignore $WEBLOG_FOLDER/
fi

if [[ -z "${DOCKER_PLATFORM:-}" ]]; then

    ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')

    case $ARCH in
        arm64|aarch64) DOCKER_PLATFORM_ARGS="${DOCKER_PLATFORM:-"--platform linux/arm64/v8"}";;
        *)             DOCKER_PLATFORM_ARGS="${DOCKER_PLATFORM:-"--platform linux/amd64"}";;
    esac
fi


echo "Building docker weblog image using variant [${WEBLOG_VARIANT}] and library [${TEST_LIBRARY}]"
CURRENT_DIR=$(pwd)
cd $WEBLOG_FOLDER

if [ -n "${PUSH_TAG+set}" ]; then
  docker buildx build ${DOCKER_PLATFORM} -t ${PUSH_TAG} . --push
else
    docker build ${DOCKER_PLATFORM} -t weblog-injection:latest .
fi
cd $CURRENT_DIR