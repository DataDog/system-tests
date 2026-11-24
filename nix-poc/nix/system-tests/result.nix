# A scenario run as a derivation: the build runs the run's entrypoint (./dind-run.nix) in a
# privileged docker:dind container, through the Docker daemon of the machine that builds it, and
# its output is the run's logs. A failing test fails the build. So `nix build` runs scenarios in
# parallel (max-jobs) or on remote builders, and a run whose inputs did not change is not run
# again: its result is already in the store, or substituted from a binary cache.
#
# The run is hermetic but for that daemon (see ./scenario.nix): no network, a fixed hostname, an
# empty environment for pytest, nothing read from the host. The build talks to the daemon, so it
# needs a builder that lets it:
#
#   system-features = docker                              the builder offers it (requiredSystemFeatures)
#   extra-sandbox-paths = /var/run/docker.sock            the socket, inside the build sandbox
#
# and the build users must be allowed on the socket (e.g. the nixbld group in the docker group).
# The daemon bind-mounts /nix/store into the container: the builder's store must be the daemon's
# host's. A builder whose store the daemon sees in a volume instead (./linux-nix.nix) says so in
# /etc/system-tests/store-volume.
#
# The daemon's cgroup version is a component system-tests applies manifests to: the build fails
# on a daemon whose version is not `cgroupVersion`, rather than produce another result.
{
  lib,
  runCommand,
  docker-client,
  dind-image,
}:
{
  # A scenario-runs.<SCENARIO>.<variant>.
  run,
  scenario,
  variant,
  cgroupVersion ? "2",
}:
runCommand "system-tests-${lib.toLower scenario}-${variant}-result"
  {
    nativeBuildInputs = [ docker-client ];
    requiredSystemFeatures = [ "docker" ];
    passthru = { inherit run scenario variant; };
  }
  ''
    export HOME="$TMPDIR"

    cgroup="$(docker info --format '{{.CgroupVersion}}')"
    if [ "$cgroup" != ${cgroupVersion} ]; then
      echo "the Docker daemon has cgroup v$cgroup, this result is for v${cgroupVersion}" >&2
      exit 1
    fi
    docker image inspect docker:28-dind > /dev/null 2>&1 || docker load < ${dind-image} > /dev/null

    if [ -f /etc/system-tests/store-volume ]; then
      store="$(cat /etc/system-tests/store-volume):/nix:ro"
    else
      store=/nix/store:/nix/store:ro
    fi

    # Not --rm: the logs are copied out of the container's /work once it has exited.
    container="system-tests-${lib.toLower scenario}-${variant}-$$-$RANDOM"
    trap 'docker rm --force --volumes "$container" > /dev/null 2>&1 || true' EXIT
    status=0
    docker run --privileged --network none --hostname system-tests --name "$container" \
      -v "$store" --entrypoint ${run} docker:28-dind || status=$?
    if [ "$status" != 0 ]; then
      echo "${scenario} failed on ${variant} (status $status)" >&2
      exit "$status"
    fi
    mkdir "$out"
    docker cp --quiet "$container":/work/. "$out"
  ''
