#!/usr/bin/env bash

#This script allows to build and run Docker SSI images for weblog variants to test different features of SSI.
#This script creates the test matrix (weblog variants, base images, archs, installable runtimes) and runs the tests for each combination.

set -e

BASE_DIR=$(pwd)

print_usage() {
    echo -e "${WHITE_BOLD}DESCRIPTION${NC}"
    echo -e "  Builds and run Docker SSI images for weblog variants to test different features of SSI."
    echo
    echo -e "${WHITE_BOLD}USAGE${NC}"
    echo -e "  ${SCRIPT_NAME} [options...]"
    echo
    echo -e "${WHITE_BOLD}OPTIONS${NC}"
    echo -e "  ${CYAN}--library <lib>${NC}                          Language of the tracer (env: TEST_LIBRARY, default: ${DEFAULT_TEST_LIBRARY})."
    echo -e "  ${CYAN}--weblog-variant <var>${NC}                   Weblog variant (env: WEBLOG_VARIANT)."
    echo -e "  ${CYAN}--arch${NC}                                   Build docker image architecture (env: ARCH)."
    echo -e "  ${CYAN}--force-build${NC}                            Force the image build (not use the ghcr images)."
    echo -e "  ${CYAN}--push-base-images${NC}                       Push the base images to the registry."
    echo -e "  ${CYAN}--help${NC}                                   Prints this message and exits."
    echo
    echo -e "${WHITE_BOLD}EXAMPLES${NC}"
    echo -e "  Build and run all java-app weblog combinations"
    echo -e "    utils/build/ssi/build_local.sh java -w java-app "
    echo -e "  Build and run all java-app weblog combinations for arm64 arch:"
    echo -e "    utils/build/ssi/build_local.sh java -w java-app -a linux/arm64"
    echo -e "  Force build and run all java-app weblog combinations for arm64 arch:"
    echo -e "    utils/build/ssi/build_local.sh java -w java-app -a linux/arm64 --force-build true"
    echo
}


while [[ "$#" -gt 0 ]]; do
    case $1 in
        dotnet|java|nodejs|php|python|ruby) TEST_LIBRARY="$1";;
        -l|--library) TEST_LIBRARY="$2"; shift ;;
        -r|--installable-runtime) INSTALLABLE_RUNTIME="$2"; shift ;;
        -w|--weblog-variant) WEBLOG_VARIANT="$2"; shift ;;
        -a|--arch) ARCH="$2"; shift ;;
        -f|--force-build) FORCE_BUILD="$2"; shift ;;
        -p|--push-base-images) PUSH_BASE_IMAGES="$2"; shift ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1 ;;
    esac
    shift
done

cd "${BASE_DIR}" || exit
matrix_json=$(python utils/docker_ssi/docker_ssi_matrix_builder.py --format json)

extra_args=""
if [ -n "$FORCE_BUILD" ]; then
    extra_args="--ssi-force-build"
fi
if [ -n "$PUSH_BASE_IMAGES" ]; then
    extra_args="--ssi-push-base-images"
fi

while read -r row
do
  weblog=$(echo "$row" | jq -r .weblog)
  base_image=$(echo "$row" | jq -r .base_image)
  arch=$(echo "$row" | jq -r .arch)
  installable_runtime=$(echo "$row" | jq -r .installable_runtime)
  if [ -n "$INSTALLABLE_RUNTIME" ] && [ "$INSTALLABLE_RUNTIME" != "$installable_runtime" ]; then
      continue
  fi
  if [ -n "$WEBLOG_VARIANT" ] && [ "$WEBLOG_VARIANT" != "$weblog" ]; then
      continue
  fi
  if [ -n "$ARCH" ] && [ "$ARCH" != "$arch" ]; then
      continue
  fi

  echo "Runing test scenario for weblog [${weblog}], base_image [${base_image}], arch [${arch}], installable_runtime [${installable_runtime}], extra_args: [${extra_args}]"
  ./run.sh DOCKER_SSI --ssi-weblog "$weblog" --ssi-library "$TEST_LIBRARY" --ssi-base-image "$base_image" --ssi-arch "$arch" --ssi-installable-runtime "$installable_runtime" "$extra_args"

done < <(echo "$matrix_json" | jq -c ".${TEST_LIBRARY}.parallel.matrix[]")
