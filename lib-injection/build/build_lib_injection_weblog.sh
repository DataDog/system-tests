#!/usr/bin/env bash
set -e

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
echo "SCRIPT_DIR: $SCRIPT_DIR"

# Initialize colors for output
WHITE_BOLD='\033[1;37m'
CYAN='\033[0;36m'
NC='\033[0m'

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
    echo -e "  ${CYAN}--docker-platform <platform>${NC}      Target Docker platform(s) (comma-separated)."
    echo -e "  ${CYAN}-h, --help${NC}                Display this help message."
    echo -e ""
    echo -e ""
}

# Initialize Docker Buildx
setup_buildx() {
    echo "Setting up Docker Buildx..."
    # Create a new builder instance if it doesn't exist
    if ! docker buildx inspect dd-builder >/dev/null 2>&1; then
        docker buildx create --name dd-builder --driver docker-container --bootstrap
    fi
    # Use the builder
    docker buildx use dd-builder
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        cpp|dotnet|golang|java|java_otel|nodejs|nodejs_otel|php|python|python_otel|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -dp|--docker-platform) DOCKER_PLATFORM="$2"; shift ;;
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

# Set default platform if not specified
if [[ -z "${DOCKER_PLATFORM:-}" ]]; then
    ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
    case $ARCH in
        arm64|aarch64) DOCKER_PLATFORM="linux/arm64/v8";;
        *)             DOCKER_PLATFORM="linux/amd64";;
    esac
fi

# Convert comma-separated platforms to buildx format
PLATFORM_ARGS=""
for platform in $(echo $DOCKER_PLATFORM | tr ',' ' '); do
    PLATFORM_ARGS="$PLATFORM_ARGS --platform $platform"
done

echo "Building docker weblog image using variant [${WEBLOG_VARIANT}] and library [${TEST_LIBRARY}]"
echo "Target platforms: ${DOCKER_PLATFORM}"

# Setup buildx
setup_buildx

CURRENT_DIR=$(pwd)
cd $WEBLOG_FOLDER

# Build the image
if [ -n "${PUSH_TAG+set}" ]; then
    echo "Building and pushing image to ${PUSH_TAG}"
    docker buildx build ${PLATFORM_ARGS} -t ${PUSH_TAG} . --push
else
    echo "Building local image"
    docker buildx build ${PLATFORM_ARGS} -t weblog-injection:latest --load .
fi

cd $CURRENT_DIR