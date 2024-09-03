#!/usr/bin/env bash

set -e

#11.0.24-zulu

#docker buildx build -f base/base_lang.Dockerfile  -t ubuntu_22:java_11 --build-arg BASE_IMAGE=ubuntu:22.04 --build-arg ARCH=linux/amd64 --build-arg LANG=java --build-arg RUNTIME_VERSIONS=11.0.24-zulu --load .

#docker buildx build -f base/base_ssi.Dockerfile  -t ssi_ubuntu_22:java_11 --build-arg BASE_IMAGE=ubuntu_22:java_11 --build-arg ARCH=linux/amd64 --build-arg LANG=java --load .

#docker buildx build -f java/dd-lib-java-init-test-app.Dockerfile --build-context lib_injection=../../../lib-injection/build/docker --build-arg BASE_IMAGE=ssi_ubuntu_22:java_11 -t weblog-injection:latest --load .

#docker buildx build -f java/java7-app.Dockerfile --build-context lib_injection=../../../lib-injection/build/docker --build-arg BASE_IMAGE=ssi_ubuntu_22:java_11 -t weblog-injection:latest --load .

#docker buildx build --platform linux/arm64 -f java/tomcat-app.Dockerfile --build-context lib_injection=../../../lib-injection/build/docker  -t weblog-injection:latest --load .

DEFAULT_ARCH="linux/amd64"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "${SCRIPT_DIR}" || exit

print_usage() {
    echo -e "${WHITE_BOLD}DESCRIPTION${NC}"
    echo -e "  Builds Docker SSI images for weblog variants to test different features of SSI."
    echo
    echo -e "${WHITE_BOLD}USAGE${NC}"
    echo -e "  ${SCRIPT_NAME} [options...]"
    echo
    echo -e "${WHITE_BOLD}OPTIONS${NC}"
    echo -e "  ${CYAN}--library <lib>${NC}                          Language of the tracer (env: TEST_LIBRARY, default: ${DEFAULT_TEST_LIBRARY})."
    echo -e "  ${CYAN}--weblog-variant <var>${NC}                   Weblog variant (env: WEBLOG_VARIANT)."
    echo -e "  ${CYAN}--base-image <base docker image>${NC}         Name of the base image. For example ubuntu:22.04. Check the allowed based images using the command 'build.sh --list-allowed-base-images'."
    echo -e "  ${CYAN}--arch${NC}                                   Build docker image architecture (env: DEFAULT_ARCH, default: ${DEFAULT_ARCH})."
    echo -e "  ${CYAN}----runtime_version <args>${NC}               Runtime language version to install. Depends of the language (TEST_LIBRARTY) For example: 11.0.24-zulu. Check the allowed versions of the language using the command 'build.sh --list-allowed-runtimes'."
    echo -e "  ${CYAN}--help${NC}                                   Prints this message and exits."
    echo
    echo -e "${WHITE_BOLD}EXAMPLES${NC}"
    echo -e "  Build a java weblog based on ubuntu:22.04 with java runtime version 11.0.24-zulu:"
    echo -e "    ./build.sh java -w dd-lib-java-init-test-app --base-image ubuntu:22.04 --runtime_version 11.0.24-zulu"
    echo -e "  Build a java weblog based on ubuntu:22.04 AMD64 with java runtime version 11.0.24-zulu:"
    echo -e "    ./build.sh java -w dd-lib-java-init-test-app --base-image ubuntu:22.04 --runtime_version 11.0.24-zulu --arch linux/amd64"
    echo
    echo -e "More info at https://github.com/DataDog/system-tests/blob/main/docs/execute/build.md"
    echo
}


while [[ "$#" -gt 0 ]]; do
    case $1 in
        dotnet|java|nodejs|php|python|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -b|--base-image) BASE_IMAGE="$2"; shift ;;
        -a|--arch) ARCH="$2"; shift ;;
        -r|--runtime_version) RUNTIME_VERSIONS="$2"; shift ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1 ;;
    esac
    shift
done

if [ -z "${WEBLOG_VARIANT-}" ]; then
   echo "Must provide the weblog variant (Use -w or --weblog-variant parameter). Exiting...."
   exit 1
fi

if [ -z "${TEST_LIBRARY-}" ]; then
   echo "Must provide the TEST_LIBRARY (Use -l or --library parameter). Exiting...."
   exit 1
fi

if [ -z "${ARCH-}" ]; then
   ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
    case $ARCH in
    arm64|aarch64) ARCH="linux/arm64/v8";;
    *)             ARCH="linux/amd64";;
    esac
fi

if [ -z "${BASE_IMAGE-}" ]; then
   docker buildx build --platform "${ARCH}" -f "${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile" --build-context lib_injection=../../../lib-injection/build/docker  -t weblog-injection:latest --load .
else
    #TODO check the base image is correct
    #TODO check the runtime version is correct
    #TODO check the weblog variant is correct

    TAG=$(echo "${BASE_IMAGE}" | tr ":" "_")
    TAG="${TAG}:${TEST_LIBRARY}_${RUNTIME_VERSIONS}"
    echo "Building from base image ${BASE_IMAGE} with tag: ${TAG} and ARCH: ${ARCH}"

    if [ -z "${RUNTIME_VERSIONS-}" ]; then
        echo "Must provide the runtime version of the language to be installed on the base image. Please use the command 'build.sh --list-allowed-runtimes' to check the available runtimes. Exiting...."
        exit 1
    fi
    docker buildx build -f base/base_lang.Dockerfile  -t "${TAG}" --build-arg BASE_IMAGE="${BASE_IMAGE}" --build-arg ARCH="${ARCH}" --build-arg LANG="${TEST_LIBRARY}" --build-arg RUNTIME_VERSIONS="${RUNTIME_VERSIONS}" --load .
    docker buildx build -f base/base_ssi.Dockerfile  -t "ssi_${TAG}" --build-arg BASE_IMAGE="${TAG}" --build-arg ARCH="${ARCH}" --build-arg LANG="${TEST_LIBRARY}" --load .
    docker buildx build -f "${TEST_LIBRARY}/${WEBLOG_VARIANT}.Dockerfile" --build-context lib_injection=../../../lib-injection/build/docker --build-arg BASE_IMAGE="ssi_${TAG}" -t weblog-injection:latest --load .
fi
 #BASE_IMAGE=ubuntu:22.04
 #ARCH=linux/amd64
 #RUNTIME_VERSIONS=11.0.24-zulu
 #WEBLOG_NAME

echo "Weblog build DONE!"