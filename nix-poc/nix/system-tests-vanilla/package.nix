# The final package (Linux): `runs.<SCENARIO>.<variant>`, whose closure is everything a run
# needs, so it runs with nothing from outside but the Docker daemon it starts its dind on:
#
#   bin/system-tests-vanilla-<scenario>-<variant> [--docker-host URL] [--workdir DIR]
#       [--store-volume NAME] [-- pytest arguments]
#
#   --docker-host   the daemon (default unix:///var/run/docker.sock)
#   --workdir       where the outputs go, a path the daemon can bind-mount
#                   (default ./system-tests-vanilla-<SCENARIO>-<variant>)
#   --store-volume  a Docker volume holding the store at /nix, for daemons that do not see this
#                   store at /nix/store (linux-nix's, from macOS)
#
# It re-executes itself under `env -i` first: the host's environment, home and Docker
# configuration (contexts, credentials) are not read; the docker CLI gets an empty config. It
# then starts the pinned docker:dind (its tarball is in the closure, loaded unless the daemon has
# it) privileged, with `--network none` and the store mounted read-only, running the entrypoint
# below: the container's dockerd, `docker events` recorded, then the core (./core.nix) on /work:
#
#   <workdir>/logs/               system-tests' logs (logs_<scenario> for other scenarios)
#   <workdir>/dockerd.log         the run's daemon log
#   <workdir>/docker-events.json  every daemon event of the run (no `pull` among them)
{
  lib,
  writeShellScript,
  writeShellApplication,
  docker-client,
  coreutils,
  dind-image,
}:
{
  scenario,
  variant,
  core,
}:
let
  name = "system-tests-vanilla-${lib.toLower scenario}-${variant}";

  # What the dind container runs; docker and dockerd-entrypoint.sh are the pinned image's.
  entrypoint = writeShellScript "${name}-dind-entrypoint" ''
    set -euo pipefail
    export PATH=/usr/local/bin:/usr/bin:/bin
    mkdir -p /work
    rm -f /work/dockerd.log /work/docker-events.json
    dockerd-entrypoint.sh dockerd > /work/dockerd.log 2>&1 &
    for _ in $(seq 60); do
      docker info > /dev/null 2>&1 && break
      sleep 1
    done
    docker info > /dev/null
    docker events --format '{{json .}}' > /work/docker-events.json &
    events=$!
    status=0
    ${core} /work "$@" || status=$?
    sleep 1
    kill "$events" 2> /dev/null || true
    pulls="$(grep -c '"Action":"pull"' /work/docker-events.json || true)"
    echo "image pulls during the run: $pulls (see docker-events.json)" >&2
    exit "$status"
  '';
in
writeShellApplication {
  inherit name;
  runtimeInputs = [
    docker-client
    coreutils
  ];
  text = ''
    if [ -z "''${SYSTEM_TESTS_VANILLA_CLEAN_ENV:-}" ]; then
      exec ${coreutils}/bin/env -i SYSTEM_TESTS_VANILLA_CLEAN_ENV=1 "''${BASH_SOURCE[0]}" "$@"
    fi
    unset SYSTEM_TESTS_VANILLA_CLEAN_ENV
    export PATH=${
      lib.makeBinPath [
        docker-client
        coreutils
      ]
    }

    host=unix:///var/run/docker.sock
    workdir=./system-tests-vanilla-${scenario}-${variant}
    store=(-v /nix/store:/nix/store:ro)
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --docker-host) host="$2"; shift 2 ;;
        --workdir) workdir="$2"; shift 2 ;;
        --store-volume) store=(-v "$2:/nix:ro"); shift 2 ;;
        --) shift; break ;;
        *) echo "unknown argument $1 (pytest arguments go after --)" >&2; exit 2 ;;
      esac
    done
    mkdir -p "$workdir"
    workdir="$(realpath "$workdir")"

    HOME="$(mktemp -d)"
    trap 'rm -rf "$HOME"' EXIT
    export HOME DOCKER_HOST="$host" DOCKER_CONFIG="$HOME/.docker"

    docker image inspect docker:28-dind > /dev/null 2>&1 || docker load < ${dind-image} > /dev/null
    echo "running ${scenario} on ${variant} with its own Docker daemon, logs in $workdir" >&2
    docker run --rm --privileged --network none --hostname system-tests \
      --name "${name}-$$-$RANDOM" \
      "''${store[@]}" -v "$workdir":/work \
      --entrypoint ${entrypoint} docker:28-dind "$@"
  '';
  passthru = {
    inherit
      scenario
      variant
      core
      entrypoint
      ;
  };
}
