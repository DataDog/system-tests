#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT_DIR="$SCRIPT_DIR/../.."
readonly BINARIES_DIR="$ROOT_DIR/binaries"

export GOPATH="$BINARIES_DIR/go"
export GO111MODULE=off

function git_clone_or_update() {
    local -r repo="$1" path="$2"
    echo "Updating $repo"
    if [[ ! -e "$path" ]]; then
        git clone --depth 1 "${repo}" "${path}"
    else
        pushd "$path" &>/dev/null
        # Avoid dirty tree
        git checkout -f
        git pull --depth 1 --rebase --allow-unrelated-histories
        popd &>/dev/null
    fi
}

echo "go get github.com/gogo/protobuf/gogoproto"
go get github.com/gogo/protobuf/gogoproto

mkdir -p "$GOPATH/src/github.com/DataDog"
git_clone_or_update https://github.com/DataDog/datadog-agent.git "$GOPATH/src/github.com/DataDog/datadog-agent"
git_clone_or_update https://git@github.com/DataDog/agent-payload.git "$GOPATH/src/github.com/DataDog/agent-payload"

# Remove gogo references to avoid getting RegisterExtension, which is not supported in Python.
sed -e 's~ \[(gogo.*\]~~g' \
    -e '/import.*gogo/d' \
    -i \
    "$GOPATH/src/github.com/DataDog/datadog-agent/pkg/proto/datadog/trace/agent_payload.proto" \
    "$GOPATH/src/github.com/DataDog/agent-payload/proto/metrics/agent_payload.proto"

protoc \
    --include_imports \
    "-I$GOPATH/src" \
    "-I$GOPATH/src/github.com/gogo/protobuf/protobuf" \
    "-I$GOPATH/src/github.com/DataDog/datadog-agent/pkg/proto" \
    "-I$GOPATH/src/github.com/DataDog/agent-payload/proto" \
    --descriptor_set_out="$ROOT_DIR/utils/proxy/_decoders/agent.descriptor" \
    "$GOPATH/src/github.com/DataDog/datadog-agent/pkg/proto/datadog/trace/agent_payload.proto" \
    "$GOPATH/src/github.com/DataDog/agent-payload/proto/metrics/agent_payload.proto"
