#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
echo "SCRIPT_DIR: ${SCRIPT_DIR}"

# Initialize colors for output
WHITE_BOLD='\033[1;37m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# Retry configuration
MAX_RETRIES=${MAX_RETRIES:-3}
INITIAL_DELAY=${INITIAL_DELAY:-5}
BUILD_TIMEOUT=${BUILD_TIMEOUT:-1200}  # 20 minutes timeout in seconds
TIMEOUT_COMMAND=$(command -v timeout || command -v gtimeout || true)

print_usage() {
    echo -e "${WHITE_BOLD}DESCRIPTION${NC}"
    echo -e "  Builds Docker images for weblog variants with tracers extracted from lib injection init images."
    echo
    echo -e "${WHITE_BOLD}USAGE${NC}"
    echo -e "  ${0} [options...]"
    echo
    echo -e "${WHITE_BOLD}OPTIONS${NC}"
    echo -e "  ${CYAN}--library <lib>${NC}            Language of the tracer (env: TEST_LIBRARY, Mandatory)"
    echo -e "  ${CYAN}--weblog-variant <var>${NC}     Weblog variant (env: WEBLOG_VARIANT). (Mandatory)"
    echo -e "  ${CYAN}--push-tag <var>${NC}     The image will be pushed to docker registry (env: PUSH_TAG)."
    echo -e "  ${CYAN}--docker-platform <platform>${NC}      Target Docker platform(s) (comma-separated)."
    echo -e "  ${CYAN}--max-retries <num>${NC}        Maximum number of retry attempts (env: MAX_RETRIES, default: 3)"
    echo -e "  ${CYAN}--initial-delay <seconds>${NC}  Initial delay between retries in seconds (env: INITIAL_DELAY, default: 5)"
    echo -e "  ${CYAN}--build-timeout <seconds>${NC}  Docker build timeout in seconds (env: BUILD_TIMEOUT, default: 1200)"
    echo -e "  ${CYAN}-h, --help${NC}                Display this help message."
    echo -e ""
    echo -e ""
}

# Create the buildx builder used by this script. A failed attempt can leave
# the builder unusable, so callers remove it before retrying.
setup_buildx() {
    echo "Setting up Docker Buildx..."
    if ! docker buildx inspect dd-builder >/dev/null 2>&1; then
        docker buildx create --name dd-builder --driver docker-container --bootstrap || return $?
    fi
    docker buildx use dd-builder
}

# Run a docker buildx command. Retry builder setup and the build. Remove
# dd-builder after a failure so the next attempt does not reuse a broken builder.
run_docker_build() {
    local -a build_cmd=("$@")
    local attempt=1
    local delay="${INITIAL_DELAY}"
    local exit_code=1

    echo -e "${YELLOW}Starting Docker build (max ${MAX_RETRIES} attempts, ${BUILD_TIMEOUT}s timeout per attempt)${NC}"

    while [[ "${attempt}" -le "${MAX_RETRIES}" ]]; do
        echo -e "${CYAN}Attempt ${attempt}/${MAX_RETRIES}${NC}"

        set +e
        setup_buildx
        exit_code=$?
        if [[ "${exit_code}" -eq 0 ]]; then
            if [[ -n "${TIMEOUT_COMMAND}" ]]; then
                "${TIMEOUT_COMMAND}" "${BUILD_TIMEOUT}" "${build_cmd[@]}"
            else
                echo "No timeout command found; running the build without a per-attempt timeout"
                "${build_cmd[@]}"
            fi
            exit_code=$?
        fi
        set -e

        if [[ "${exit_code}" -eq 0 ]]; then
            echo -e "${GREEN}Docker build succeeded on attempt ${attempt}${NC}"
            return 0
        fi

        if [[ "${exit_code}" -eq 124 ]]; then
            echo -e "${RED}Docker build timed out after ${BUILD_TIMEOUT} seconds on attempt ${attempt}${NC}"
        else
            echo -e "${RED}Docker build failed on attempt ${attempt} with exit code ${exit_code}${NC}"
        fi

        if [[ "${attempt}" -eq "${MAX_RETRIES}" ]]; then
            echo -e "${RED}Docker build failed after ${MAX_RETRIES} attempts${NC}"
            return "${exit_code}"
        fi

        echo -e "${YELLOW}Removing buildx builder dd-builder before retry${NC}"
        docker buildx rm --force dd-builder >/dev/null 2>&1 || true

        echo -e "${YELLOW}Waiting ${delay} seconds before retry${NC}"
        sleep "${delay}"
        delay=$((delay * 2))
        attempt=$((attempt + 1))
    done

    return "${exit_code}"
}

VALID_LIBRARIES=$(python3 utils/const/__main__.py COMPONENT_GROUPS lib_injection)

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -dp|--docker-platform) DOCKER_PLATFORM="$2"; shift ;;
        -pt|--push-tag) PUSH_TAG="$2"; shift ;;
        --max-retries) MAX_RETRIES="$2"; shift ;;
        --initial-delay) INITIAL_DELAY="$2"; shift ;;
        --build-timeout) BUILD_TIMEOUT="$2"; shift ;;
        -h|--help) print_usage; exit 0 ;;
        *)
            if [[ "$1" =~ ^(${VALID_LIBRARIES})$ ]]; then
                TEST_LIBRARY="$1"
            else
                echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1
            fi
            ;;
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

if [[ "${TEST_LIBRARY}" == "ruby" ]]; then
    cp -r "${WEBLOG_FOLDER}/../lib_injection_rails_app" "${WEBLOG_FOLDER}/lib_injection_rails_app"
    cp "${WEBLOG_FOLDER}/../.dockerignore" "${WEBLOG_FOLDER}/"
fi

# If no platform is specified, use the host architecture.
if [[ -z "${DOCKER_PLATFORM:-}" ]]; then
    ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
    case $ARCH in
        arm64|aarch64) DOCKER_PLATFORM="linux/arm64/v8";;
        *)             DOCKER_PLATFORM="linux/amd64";;
    esac
fi

# Convert comma-separated platforms to buildx arguments.
platform_args=()
IFS=',' read -r -a platforms <<< "${DOCKER_PLATFORM}"
for platform in "${platforms[@]}"; do
    if [[ -n "${platform}" ]]; then
        platform_args+=(--platform "${platform}")
    fi
done

echo "Building docker weblog image using variant [${WEBLOG_VARIANT}] and library [${TEST_LIBRARY}]"
echo "Target platforms: ${DOCKER_PLATFORM}"

CURRENT_DIR=$(pwd)
cd "${WEBLOG_FOLDER}"

if [ -n "${PUSH_TAG+set}" ]; then
    echo "Building and pushing image to ${PUSH_TAG}"
    run_docker_build docker buildx build "${platform_args[@]}" -t "${PUSH_TAG}" . --push
else
    echo "Building local image"
    run_docker_build docker buildx build "${platform_args[@]}" -t weblog-injection:latest --load .
fi

cd "${CURRENT_DIR}"
