#!/usr/bin/env bash
# Helper script to pin and download Maven dependencies.
# To refresh the lock files, run:
#   ./install_dependencies.sh --pin-all
set -eu

readonly PROG="$0"

if [[ "${1:-}" = --pin-all ]]; then
    find -name '*.Dockerfile' | while read dockerfile; do
        echo "$dockerfile"
        src_dir="$(grep '^COPY.*/pom.xml' "$dockerfile" | head -n 1 | sed -e 's~/pom.xml.*~~g' -e 's~.*/~~g')"
        if [[ -z ${src_dir} ]]; then
            continue
        fi
        echo "src_dir: $src_dir"
        cmd="$(grep '^RUN ./install_dependencies.sh' "$dockerfile" | sed -e 's~RUN ./install_dependencies.sh~~g' | head -n 1)"
        if [[ -z ${cmd} ]]; then
            continue
        fi
        pushd "$src_dir"
        rm -rf tmp_repo
        export MAVEN_REPO=tmp_repo
        "../$PROG" $cmd
        popd
    done
    exit 0
fi

readonly LOCK_FILE="${1:-}"
shift
readonly MAVEN_REPO="${MAVEN_REPO}"
readonly EXTRA_MVN_ARGS=("$@")

declare -a MVN_COMMAND=(mvn -B package)
MVN_COMMAND+=("${EXTRA_MVN_ARGS[@]}")

readonly CURL_CONFIG=.curl-config

export MAVEN_OPTS="${MAVEN_OPTS:-} -Dmaven.repo.local=$MAVEN_REPO"

try_download_from_repo() {
    local repo="${1}" dest
    cat "${LOCK_FILE}" | while read line; do
        dest="$MAVEN_REPO/$line"
        if [[ ! -f "$dest" ]]; then
            echo "url = $repo/$line"
            echo "output = $MAVEN_REPO/$line"
        fi
    done >"$CURL_CONFIG"
    if [[ $(cat "$CURL_CONFIG" | wc -l) -eq 0 ]]; then
        # Nothing to fetch
        return
    fi
    # TODO: Once we have newer curl: --remove-on-error
    curl --fail --no-progress-meter --create-dirs --location --config "$CURL_CONFIG" || true
}

if [[ ! -f ${LOCK_FILE} ]]; then
    "${MVN_COMMAND[@]}" || true

    for path in $(find "$MAVEN_REPO" -type f | sort); do
        if [[ $path =~ .*(.lastUpdated|_remote.repositories|resolver-status.properties) ]]; then
            continue
        fi
        rel="$(realpath --relative-to="$MAVEN_REPO" "$path")"
        echo "$rel"
    done >"$LOCK_FILE"
else
    try_download_from_repo https://repo.maven.apache.org/maven2
    try_download_from_repo https://repo.spring.io/release
    "${MVN_COMMAND[@]}" || true
fi
