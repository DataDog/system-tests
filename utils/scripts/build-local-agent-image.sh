#!/usr/bin/env bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

##########################################################################################
# Build a datadog-agent Docker image whose trace-agent binary is compiled from a LOCAL
# datadog-agent checkout/worktree, overlaid on a published agent base image.
#
# This is a fast shortcut for iterating on pkg/trace or cmd/trace-agent without waiting
# for a datadog-agent CI image build, and without needing `dda inv agent.hacky-dev-image-build`
# (which builds host-native binaries + rtloader and requires a Linux devcontainer on macOS).
#
# Only the trace-agent binary is replaced -- this is enough for most APM/tracing
# system-tests scenarios. If your changes touch code outside pkg/trace or cmd/trace-agent,
# use `dda inv agent.hacky-dev-image-build` (from a Linux devcontainer) or a CI-built
# datadog-agent image instead.
#
# See docs/execute/binaries.md for how to wire the resulting image into system-tests.
##########################################################################################

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: build-local-agent-image.sh [OPTIONS] [AGENT_SRC] [IMAGE]

Build a datadog-agent image with a trace-agent binary compiled from a local
datadog-agent checkout, overlaid on a published base image.

Arguments (may also be given as options):
  AGENT_SRC             Path to a local datadog-agent checkout/worktree.
                         Env: AGENT_SRC
  IMAGE                 Tag for the resulting image, e.g. datadog/agent-dev:my-branch
                         Env: IMAGE

Options:
  -s, --agent-src PATH   Same as the AGENT_SRC positional argument.
  -i, --image TAG        Same as the IMAGE positional argument.
  -b, --base-image REF   Base agent image to overlay onto. Default: datadog/agent-dev:master-py3
                         Env: BASE_IMAGE
  -h, --help             Show this help and exit.

Environment variables:
  BASE_IMAGE      Base agent image (default: datadog/agent-dev:master-py3)
  PLATFORM        Docker platform to build for (default: linux/<docker server arch>)
  AGENT_VERSION   Override the version baked into the binary (default: derived from
                  BASE_IMAGE's own trace-agent)
  GOMODCACHE      Host Go module cache to mount (default: $GOPATH/pkg/mod or
                  $HOME/go/pkg/mod)

Examples:
  ./utils/scripts/build-local-agent-image.sh ~/dev/datadog-agent datadog/agent-dev:my-branch
  ./utils/scripts/build-local-agent-image.sh --agent-src ~/dev/datadog-agent \
      --image datadog/agent-dev:my-branch

After building, wire the image into system-tests:
  echo datadog/agent-dev:my-branch > binaries/agent-image
  ./build.sh <library>
  TEST_LIBRARY=<library> ./run.sh DEFAULT
EOF
}

AGENT_SRC="${AGENT_SRC:-}"
IMAGE="${IMAGE:-}"
BASE_IMAGE="${BASE_IMAGE:-datadog/agent-dev:master-py3}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s | --agent-src)
            AGENT_SRC="$2"
            shift 2
            ;;
        -i | --image)
            IMAGE="$2"
            shift 2
            ;;
        -b | --base-image)
            BASE_IMAGE="$2"
            shift 2
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            if [[ -z "$AGENT_SRC" ]]; then
                AGENT_SRC="$1"
            elif [[ -z "$IMAGE" ]]; then
                IMAGE="$1"
            else
                echo "Unexpected extra argument: $1" >&2
                usage >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$AGENT_SRC" ]]; then
    echo "error: missing datadog-agent source path." >&2
    echo "Pass it as the first argument, --agent-src, or the AGENT_SRC env var." >&2
    exit 1
fi

if [[ -z "$IMAGE" ]]; then
    echo "error: missing output image tag." >&2
    echo "Pass it as the second argument, --image, or the IMAGE env var." >&2
    exit 1
fi

if [[ ! -d "$AGENT_SRC" ]]; then
    echo "error: datadog-agent source path '$AGENT_SRC' does not exist or is not a directory." >&2
    exit 1
fi

if [[ ! -f "$AGENT_SRC/.go-version" ]]; then
    echo "error: '$AGENT_SRC/.go-version' not found -- is this a datadog-agent checkout?" >&2
    exit 1
fi

# Docker platform of the resulting image; must match the arch your docker VM/host runs.
PLATFORM="${PLATFORM:-linux/$(docker version --format '{{.Server.Arch}}')}"
GOARCH="${PLATFORM##*/}"

WORK="$HOME/.cache/system-tests-agent-build"
OUT="$WORK/out"
mkdir -p "$OUT" "$WORK/gocache"

GO_VERSION="$(cat "$AGENT_SRC/.go-version")"
TRACE_AGENT_TAGS="docker containerd datadog.no_waf kubelet otlp netcgo podman"
GOMODCACHE="${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"

# Match the base image's own version so system-tests' agent-version gating behaves the
# same way it would with the published image (an unset version would otherwise report
# a generic 6.0.0).
AGENT_VERSION="${AGENT_VERSION:-$(docker run --rm --entrypoint /opt/datadog-agent/embedded/bin/trace-agent "$BASE_IMAGE" version |
    sed -E 's/^trace-agent ([^ ]+).*/\1/')}"
COMMIT="$(git -C "$AGENT_SRC" rev-parse --short HEAD)"
FULL_COMMIT="$(git -C "$AGENT_SRC" rev-parse HEAD)"
VERSION_PKG=github.com/DataDog/datadog-agent/pkg/version

echo ">> building trace-agent ($AGENT_VERSION, $COMMIT) for $PLATFORM from $AGENT_SRC"
docker run --rm --platform "$PLATFORM" \
    -v "$AGENT_SRC:/src" \
    -v "$GOMODCACHE:/go/pkg/mod" \
    -v "$OUT:/out" \
    -v "$WORK/gocache:/gocache" \
    -w /src -e CGO_ENABLED=1 -e GOCACHE=/gocache -e "GOARCH=$GOARCH" \
    "golang:$GO_VERSION" \
    go build -tags "$TRACE_AGENT_TAGS" \
        -ldflags "-X $VERSION_PKG.AgentVersion=$AGENT_VERSION -X $VERSION_PKG.Commit=$COMMIT -X $VERSION_PKG.FullCommit=$FULL_COMMIT" \
        -o /out/trace-agent ./cmd/trace-agent

# The Dockerfile must live inside the (small) build context directory: using `-f` to
# point at a Dockerfile outside the context (e.g. in /tmp) fails on macOS with xattr
# permission errors.
cat >"$OUT/Dockerfile" <<EOF
FROM $BASE_IMAGE
COPY trace-agent /opt/datadog-agent/embedded/bin/trace-agent
EOF

echo ">> building image $IMAGE on $BASE_IMAGE"
docker build --platform "$PLATFORM" -t "$IMAGE" "$OUT"

echo ">> verifying built image"
docker run --rm --entrypoint /opt/datadog-agent/embedded/bin/trace-agent "$IMAGE" version

echo ">> done: $IMAGE"
echo ">> to use it with system-tests, run:"
echo "     echo $IMAGE > binaries/agent-image"
