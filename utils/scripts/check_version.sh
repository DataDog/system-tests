#!/usr/bin/env bash
set -eu

# VARIABLES TO CHANGE
library="java"
weblog_variant="spring-boot"
scenario="DEFAULT"
build_prefix="dd-java-agent"
build_suffix="jar"
test_name="tests/appsec/waf/test_addresses.py::Test_PathParams" # leave empty for all tests

readonly OUTPUT_DIR=version-check-output/$library
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/$scenario"
mkdir -p "$OUTPUT_DIR/$scenario/$weblog_variant"

declare -A SEEN_XPASS

# ADD THE VERSIONS THAT YOU WANT TO CHECK HERE
versions=(
#    0.110.0
#    0.111.0
#    0.112.0
#    0.113.0
#    0.114.0
#    0.115.0
#    1.0.0
#    1.1.0
#    1.2.0
#    1.3.0
#    1.4.0
#    1.5.0
#    1.6.0
#    1.7.0
#    1.8.0
#    1.9.0
#    1.10.0
#    1.11.0
#    1.12.0
#    1.13.0
#    1.14.0
#    1.15.0
#    1.16.0
#    1.17.0
#    1.18.0
#    1.19.0
#    1.20.0
#    1.21.0
#    1.22.0
#    1.23.0
#    1.24.0
#    1.25.1
#    1.26.0
#    1.27.0
#    1.28.0
#    1.29.0
#    1.30.0
#    1.30.1
#    1.31.0
#    1.31.1
#    1.31.2
#    1.32.0
#    1.33.0
#    1.34.0
    1.35.0
    1.35.1
    1.35.2
    1.36.0
    1.37.0
    1.37.1
    1.38.0
    1.38.1
    1.39.0
    1.39.1
    1.40.0
    1.40.1
    1.40.2
    1.41.0
    1.41.1
    1.41.2
    1.42.0
    1.42.1
    1.42.2
    1.43.0
    1.44.0
    1.44.1
    1.45.0
)

for v in "${versions[@]}"; do
    output_file="$OUTPUT_DIR/$scenario/$weblog_variant/$library-$v.txt"
    if [[ -f "$output_file" ]]; then
        echo "Skipping version $v (already tested)"
    else
        echo "Testing version $v"
        build="$build_prefix-$v.$build_suffix"
        if [ ! -f "$build" ]; then
            echo "Downloading $build"
            curl -sSLO "https://github.com/DataDog/dd-trace-$library/releases/download/v$v/$build"
        fi
        rm binaries/$build_prefix*.$build_suffix || true
        cp "$build" binaries/
        rm "$build" || true
        echo "Building $library $v $weblog_variant"
        ./build.sh --library $library --weblog-variant $weblog_variant &> /dev/null
        echo "Running $library $v $weblog_variant"
        ./run.sh --scenario $scenario $test_name &> "$OUTPUT_DIR/$scenario/$weblog_variant/$library-$v.txt" || true
    fi

    declare -A seen_xpass
    declare -A seen_fail
    while read -r test; do
        seen_xpass[$test]=1
    done < <(grep ^XPASS "$output_file" | grep -v '::test_secure ' | grep -v 'Test_Dbm::test_trace_payload_service' | grep -v '::test_empty_cookie' | awk '{ print $2 }')
    while read -r test; do
        seen_fail[$test]=1
        echo "[$v] FAIL: $test"
    done < <(grep ^FAILED "$output_file" | awk '{ print $2 }')
    for test in "${!seen_xpass[@]}"; do
        if [[ ! -v seen_fail[$test] ]]; then
            if [[ ! -v SEEN_XPASS[$test] ]]; then
                echo "[$v] XPASS: $test"
                SEEN_XPASS[$test]=1
            fi
        fi
    done
done