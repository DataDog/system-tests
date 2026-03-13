#!/usr/bin/env bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

# Prepare binaries/ for running system-tests against a locally checked-out tracer repo.
# Handles the copy/clone/pointer-file step for each supported language so you don't have
# to remember the per-language conventions documented in docs/execute/binaries.md.
#
# Usage:
#   ./utils/scripts/prepare-local-build.sh <language> <path-to-tracer-repo> [options]
#   ./utils/scripts/prepare-local-build.sh --clean [language]
#
# Examples:
#   ./utils/scripts/prepare-local-build.sh java   ~/dd/dd-trace-java
#   ./utils/scripts/prepare-local-build.sh nodejs ~/dd/dd-trace-js
#   ./utils/scripts/prepare-local-build.sh python ~/dd/dd-trace-py --method wheel
#   ./utils/scripts/prepare-local-build.sh --clean          # clean all languages
#   ./utils/scripts/prepare-local-build.sh --clean java     # clean java only

set -e
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BINARIES="${REPO_ROOT}/binaries"

function error() {
    echo "error:" "$@" 1>&2
}

function die() {
    local rc=1
    if [[ ${1} =~ ^-?[0-9]+$ ]]; then
        rc="${1}"
        shift
    fi
    error "$@"
    exit "${rc}"
}

function info() {
    echo "=>" "$@"
}

function usage() {
    cat <<'EOS'
Usage:
  prepare-local-build.sh <language> <path-to-tracer-repo> [options]
  prepare-local-build.sh --clean [language]
  prepare-local-build.sh --list
  prepare-local-build.sh --status

Languages: java, nodejs, golang, python, ruby, rust, cpp, dotnet, php

Options:
  --method <method>   Override the default preparation method for a language.
                      java:    jars (default)
                      nodejs:  local (default, volume mount), clone
                      golang:  clone (default)
                      python:  local (default, volume mount), wheel, pip, s3
                      ruby:    clone (default)
                      rust:    clone (default)
                      cpp:     clone (default)
                      dotnet:  tarball (default, copies pre-built tar.gz)
                      php:     tarball (default, copies pre-built artifacts)
  --clean [language]  Remove binaries for the given language (or all if omitted).
  --list              List supported languages and methods.
  --status            Show what's currently in binaries/.
  -h, --help          Show this help message.
EOS
}

function clean_java() {
    rm -f "${BINARIES}"/dd-java-agent-*.jar "${BINARIES}"/dd-trace-api-*.jar
    info "Cleaned Java binaries"
}

function clean_nodejs() {
    rm -f "${BINARIES}/nodejs-load-from-local" "${BINARIES}/nodejs-load-from-npm"
    rm -rf "${BINARIES}/dd-trace-js"
    info "Cleaned Node.js binaries"
}

function clean_golang() {
    rm -rf "${BINARIES}/dd-trace-go"
    rm -f "${BINARIES}/golang-load-from-go-get"
    info "Cleaned Go binaries"
}

function clean_python() {
    rm -f "${BINARIES}/python-load-from-local" "${BINARIES}/python-load-from-pip" "${BINARIES}/python-load-from-s3"
    rm -f "${BINARIES}"/ddtrace-*.whl "${BINARIES}"/ddtrace-*.tar.gz
    rm -rf "${BINARIES}/dd-trace-py"
    info "Cleaned Python binaries"
}

function clean_ruby() {
    rm -rf "${BINARIES}/dd-trace-rb"
    rm -f "${BINARIES}/ruby-load-from-bundle-add"
    info "Cleaned Ruby binaries"
}

function clean_rust() {
    rm -rf "${BINARIES}/dd-trace-rs"
    rm -f "${BINARIES}/rust-load-from-git"
    info "Cleaned Rust binaries"
}

function clean_cpp() {
    rm -rf "${BINARIES}/dd-trace-cpp"
    rm -f "${BINARIES}/cpp-load-from-git"
    info "Cleaned C++ binaries"
}

function clean_dotnet() {
    rm -f "${BINARIES}"/datadog-dotnet-apm*.tar.gz
    info "Cleaned .NET binaries"
}

function clean_php() {
    rm -f "${BINARIES}/datadog-setup.php" "${BINARIES}"/dd-library-php-*.tar.gz
    info "Cleaned PHP binaries"
}

function clean_all() {
    clean_java
    clean_nodejs
    clean_golang
    clean_python
    clean_ruby
    clean_rust
    clean_cpp
    clean_dotnet
    clean_php
}

function prepare_java() {
    local src="$1"
    local method="${2:-jars}"

    if [[ "${method}" != "jars" ]]; then
        die "Java only supports method 'jars', got '${method}'"
    fi

    # Look for pre-built JARs
    local agent_jar
    agent_jar=$(find "${src}/dd-java-agent/build/libs" -name 'dd-java-agent-*-SNAPSHOT.jar' \
        ! -name '*-sources.jar' ! -name '*-javadoc.jar' 2>/dev/null | head -1)
    local api_jar
    api_jar=$(find "${src}/dd-trace-api/build/libs" -name 'dd-trace-api-*-SNAPSHOT.jar' \
        ! -name '*-sources.jar' ! -name '*-javadoc.jar' 2>/dev/null | head -1)

    if [[ -z "${agent_jar}" || -z "${api_jar}" ]]; then
        info "JARs not found. Building with Gradle..."
        (cd "${src}" && ./gradlew :dd-java-agent:shadowJar :dd-trace-api:jar)
        agent_jar=$(find "${src}/dd-java-agent/build/libs" -name 'dd-java-agent-*-SNAPSHOT.jar' \
            ! -name '*-sources.jar' ! -name '*-javadoc.jar' | head -1)
        api_jar=$(find "${src}/dd-trace-api/build/libs" -name 'dd-trace-api-*-SNAPSHOT.jar' \
            ! -name '*-sources.jar' ! -name '*-javadoc.jar' | head -1)
    fi

    [[ -n "${agent_jar}" ]] || die "Could not find dd-java-agent JAR after build"
    [[ -n "${api_jar}" ]] || die "Could not find dd-trace-api JAR after build"

    clean_java
    cp "${agent_jar}" "${BINARIES}/"
    cp "${api_jar}" "${BINARIES}/"

    local count
    count=$(find "${BINARIES}" -name '*.jar' | wc -l | tr -d ' ')
    info "Java: copied ${count} JARs to binaries/"
    if [[ "${count}" -ne 2 ]]; then
        echo "  WARNING: expected exactly 2 JARs, found ${count}. Check binaries/ for stale files."
    fi
}

function prepare_nodejs() {
    local src="$1"
    local method="${2:-local}"

    clean_nodejs

    case "${method}" in
        local)
            # Resolve to absolute path
            local abs_path
            abs_path="$(cd "${src}" && pwd)"
            echo "${abs_path}" > "${BINARIES}/nodejs-load-from-local"
            info "Node.js: created nodejs-load-from-local -> ${abs_path}"
            info "  (volume-mounted at runtime, no rebuild needed for code changes)"
            ;;
        clone)
            git clone --depth 1 --single-branch "file://${src}" "${BINARIES}/dd-trace-js"
            info "Node.js: cloned repo into binaries/dd-trace-js"
            ;;
        *)
            die "Node.js supports methods 'local' or 'clone', got '${method}'"
            ;;
    esac
}

function prepare_golang() {
    local src="$1"
    local method="${2:-clone}"

    if [[ "${method}" != "clone" ]]; then
        die "Go only supports method 'clone', got '${method}'"
    fi

    clean_golang
    git clone --depth 1 --single-branch "file://${src}" "${BINARIES}/dd-trace-go"
    info "Go: cloned repo into binaries/dd-trace-go"
}

function prepare_python() {
    local src="$1"
    local method="${2:-local}"

    clean_python

    case "${method}" in
        local)
            local abs_path
            abs_path="$(cd "${src}" && pwd)"
            echo "${abs_path}" > "${BINARIES}/python-load-from-local"
            info "Python: created python-load-from-local -> ${abs_path}"
            info "  NOTE: native extensions (.so) must be pre-built for the target Python version."
            info "  If missing, build them with: cd ${abs_path} && scripts/ddtest 'pyenv local 3.11 && pip install -e .'"
            ;;
        wheel)
            local whl
            whl=$(find "${src}/dist" -name 'ddtrace-*.whl' 2>/dev/null | head -1)
            if [[ -z "${whl}" ]]; then
                die "No wheel found in ${src}/dist/. Build one first with: cd ${src} && scripts/ddtest 'pyenv local 3.11 && python3.11 -m pip wheel --no-deps -w dist .'"
            fi
            cp "${whl}" "${BINARIES}/"
            info "Python: copied wheel $(basename "${whl}") to binaries/"
            ;;
        pip)
            echo "ddtrace" > "${BINARIES}/python-load-from-pip"
            info "Python: created python-load-from-pip (will install latest from PyPI)"
            ;;
        s3)
            if [[ -z "${src}" ]]; then
                die "For s3 method, provide a commit hash or branch name as the path argument"
            fi
            echo "${src}" > "${BINARIES}/python-load-from-s3"
            info "Python: created python-load-from-s3 -> ${src}"
            ;;
        *)
            die "Python supports methods 'local', 'wheel', 'pip', or 's3', got '${method}'"
            ;;
    esac
}

function prepare_ruby() {
    local src="$1"
    local method="${2:-clone}"

    if [[ "${method}" != "clone" ]]; then
        die "Ruby only supports method 'clone', got '${method}'"
    fi

    clean_ruby
    git clone --depth 1 --single-branch "file://${src}" "${BINARIES}/dd-trace-rb"
    info "Ruby: cloned repo into binaries/dd-trace-rb"
}

function prepare_rust() {
    local src="$1"
    local method="${2:-clone}"

    if [[ "${method}" != "clone" ]]; then
        die "Rust only supports method 'clone', got '${method}'"
    fi

    clean_rust
    git clone --depth 1 --single-branch "file://${src}" "${BINARIES}/dd-trace-rs"
    info "Rust: cloned repo into binaries/dd-trace-rs"
}

function prepare_cpp() {
    local src="$1"
    local method="${2:-clone}"

    if [[ "${method}" != "clone" ]]; then
        die "C++ only supports method 'clone', got '${method}'"
    fi

    clean_cpp
    git clone --depth 1 --single-branch "file://${src}" "${BINARIES}/dd-trace-cpp"
    info "C++: cloned repo into binaries/dd-trace-cpp"
}

function prepare_dotnet() {
    local src="$1"
    local method="${2:-tarball}"

    if [[ "${method}" != "tarball" ]]; then
        die ".NET only supports method 'tarball', got '${method}'"
    fi

    local tarball
    tarball=$(find "${src}/tracer/src/bin/artifacts" -name 'datadog-dotnet-apm*.tar.gz' 2>/dev/null | head -1)
    if [[ -z "${tarball}" ]]; then
        die "No datadog-dotnet-apm*.tar.gz found in ${src}/tracer/src/bin/artifacts/. Build first — see docs/execute/binaries.md"
    fi

    clean_dotnet
    cp "${tarball}" "${BINARIES}/"
    info ".NET: copied $(basename "${tarball}") to binaries/"
}

function prepare_php() {
    local src="$1"
    local method="${2:-tarball}"

    if [[ "${method}" != "tarball" ]]; then
        die "PHP only supports method 'tarball', got '${method}'"
    fi

    local setup_php="${src}/datadog-setup.php"
    if [[ ! -f "${setup_php}" ]]; then
        die "datadog-setup.php not found at ${setup_php}"
    fi

    local tarball
    tarball=$(find "${src}/build/packages" -name 'dd-library-php-*-linux-gnu.tar.gz' 2>/dev/null | head -1)
    if [[ -z "${tarball}" ]]; then
        die "No dd-library-php-*-linux-gnu.tar.gz found in ${src}/build/packages/. Build the extension first."
    fi

    clean_php
    cp "${setup_php}" "${BINARIES}/"
    cp "${tarball}" "${BINARIES}/"
    info "PHP: copied datadog-setup.php and $(basename "${tarball}") to binaries/"
}

function show_status() {
    info "Current binaries/ contents:"
    local found=0

    # Java
    local jars
    jars=$(find "${BINARIES}" -maxdepth 1 -name '*.jar' 2>/dev/null)
    if [[ -n "${jars}" ]]; then
        echo "  java: $(echo "${jars}" | wc -l | tr -d ' ') JAR(s)"
        found=1
    fi

    # Node.js
    if [[ -f "${BINARIES}/nodejs-load-from-local" ]]; then
        echo "  nodejs: volume mount -> $(cat "${BINARIES}/nodejs-load-from-local")"
        found=1
    elif [[ -d "${BINARIES}/dd-trace-js" ]]; then
        echo "  nodejs: cloned repo"
        found=1
    fi

    # Go
    if [[ -d "${BINARIES}/dd-trace-go" ]]; then
        echo "  golang: cloned repo"
        found=1
    elif [[ -f "${BINARIES}/golang-load-from-go-get" ]]; then
        echo "  golang: go get -> $(cat "${BINARIES}/golang-load-from-go-get")"
        found=1
    fi

    # Python
    if [[ -f "${BINARIES}/python-load-from-local" ]]; then
        echo "  python: volume mount -> $(cat "${BINARIES}/python-load-from-local")"
        found=1
    elif ls "${BINARIES}"/ddtrace-*.whl 1>/dev/null 2>&1; then
        echo "  python: wheel"
        found=1
    elif [[ -f "${BINARIES}/python-load-from-pip" ]]; then
        echo "  python: pip -> $(cat "${BINARIES}/python-load-from-pip")"
        found=1
    fi

    # Ruby
    if [[ -d "${BINARIES}/dd-trace-rb" ]]; then
        echo "  ruby: cloned repo"
        found=1
    fi

    # Rust
    if [[ -d "${BINARIES}/dd-trace-rs" ]]; then
        echo "  rust: cloned repo"
        found=1
    fi

    # C++
    if [[ -d "${BINARIES}/dd-trace-cpp" ]]; then
        echo "  cpp: cloned repo"
        found=1
    fi

    # .NET
    if ls "${BINARIES}"/datadog-dotnet-apm*.tar.gz 1>/dev/null 2>&1; then
        echo "  dotnet: tarball"
        found=1
    fi

    # PHP
    if [[ -f "${BINARIES}/datadog-setup.php" ]]; then
        echo "  php: setup.php + tarball"
        found=1
    fi

    if [[ "${found}" -eq 0 ]]; then
        echo "  (empty — using default released versions)"
    fi
}

function show_list() {
    cat <<'EOS'
Supported languages and methods:

  java     jars      Copy pre-built JARs (builds with Gradle if missing)
  nodejs   local     Volume mount (fastest, no rebuild needed) [default]
           clone     Shallow clone into binaries/
  golang   clone     Shallow clone into binaries/ [default]
  python   local     Volume mount (requires pre-built native extensions) [default]
           wheel     Copy pre-built .whl from dist/
           pip       Install latest from PyPI
           s3        Load from S3 by commit hash
  ruby     clone     Shallow clone into binaries/ [default]
  rust     clone     Shallow clone into binaries/ [default]
  cpp      clone     Shallow clone into binaries/ [default]
  dotnet   tarball   Copy pre-built datadog-dotnet-apm*.tar.gz [default]
  php      tarball   Copy datadog-setup.php + dd-library-php*.tar.gz [default]
EOS
}

function main() {
    local language=""
    local src=""
    local method=""
    local do_clean=0

    if [[ $# -eq 0 ]]; then
        usage
        exit 0
    fi

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            --clean)
                do_clean=1
                ;;
            --list)
                show_list
                exit 0
                ;;
            --status)
                show_status
                exit 0
                ;;
            --method)
                if [[ $# -lt 2 ]]; then
                    die 64 "--method requires a value"
                fi
                method="$2"
                shift
                ;;
            -*)
                die 64 "Unknown option: $1"
                ;;
            *)
                if [[ -z "${language}" ]]; then
                    language="$1"
                elif [[ -z "${src}" ]]; then
                    src="$1"
                else
                    die 64 "Unexpected argument: $1"
                fi
                ;;
        esac
        shift
    done

    # Handle --clean
    if [[ "${do_clean}" -eq 1 ]]; then
        if [[ -n "${language}" ]]; then
            case "${language}" in
                java)    clean_java ;;
                nodejs)  clean_nodejs ;;
                golang)  clean_golang ;;
                python)  clean_python ;;
                ruby)    clean_ruby ;;
                rust)    clean_rust ;;
                cpp)     clean_cpp ;;
                dotnet)  clean_dotnet ;;
                php)     clean_php ;;
                *)       die "Unknown language: ${language}" ;;
            esac
        else
            clean_all
        fi
        exit 0
    fi

    # Validate inputs
    if [[ -z "${language}" ]]; then
        die 64 "Language is required. Run with --help for usage."
    fi

    if [[ -z "${src}" ]]; then
        die 64 "Path to tracer repo is required. Run with --help for usage."
    fi

    if [[ ! -d "${src}" ]]; then
        die "Directory not found: ${src}"
    fi

    # Dispatch to language handler
    case "${language}" in
        java)    prepare_java "${src}" "${method}" ;;
        nodejs)  prepare_nodejs "${src}" "${method}" ;;
        golang)  prepare_golang "${src}" "${method}" ;;
        python)  prepare_python "${src}" "${method}" ;;
        ruby)    prepare_ruby "${src}" "${method}" ;;
        rust)    prepare_rust "${src}" "${method}" ;;
        cpp)     prepare_cpp "${src}" "${method}" ;;
        dotnet)  prepare_dotnet "${src}" "${method}" ;;
        php)     prepare_php "${src}" "${method}" ;;
        *)       die "Unknown language: ${language}. Run with --list for supported languages." ;;
    esac

    echo ""
    info "Done! Now run your tests with:"
    echo "  TEST_LIBRARY=${language} ./run.sh PARAMETRIC -k \"<test_name>\""
    echo ""
    info "When finished, clean up with:"
    echo "  ./utils/scripts/prepare-local-build.sh --clean ${language}"
}

if [[ "$0" == "${BASH_SOURCE[0]}" ]]; then
    main "$@"
fi
