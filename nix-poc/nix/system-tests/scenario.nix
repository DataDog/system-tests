# Runs a system-tests scenario against a weblog, like `./build.sh python -w <variant>` followed by
# `./run.sh <SCENARIO>`, on the Docker daemon the docker CLI points at (`nix run`).
#
# Each run gets its own Docker daemon, in a privileged docker:dind container, with the Nix store
# mounted read-only, so runs never collide and can go in parallel (see ./dind-run.nix, the
# container's entrypoint). Everything the run uses comes from the store: the weblog, the other
# images (./images.nix), the test runner and the scenario's system-tests sources (./sources.nix).
#
# The run is hermetic but for the outer Docker daemon (and the kernel under it): the container has
# no network and a fixed hostname, pytest starts from an empty, declared environment, so the
# host's environment variables do not reach it, and /work only receives its outputs. A run is
# thus determined by the entrypoint's store path, which changes with any of the above and only
# with them, and its pytest arguments.
#
# Without arguments, the script builds the scenario's result (./result.nix): the run as a
# derivation, which Nix does not build again while its inputs stay the same (or substitutes from a
# binary cache), and links its logs as <workdir>/result. With pytest arguments, or with
# SYSTEM_TESTS_FORCE=1, it runs the entrypoint directly instead, the logs landing in <workdir> as
# the run goes; such runs are never cached.
#
#   Linux:  the entrypoint and the result's derivation are dependencies of this script,
#           /nix/store is mounted from the host
#   macOS:  both are built for the daemon's Linux with ./linux-nix.nix, whose store volume is
#           mounted
#
# The work directory is under the current one (on macOS it must be in a directory the Docker VM
# shares, such as your home). SYSTEM_TESTS_WORKDIR overrides it; give parallel runs of the same
# scenario different ones.
{
  lib,
  stdenv,
  writeShellApplication,
  docker-client,
  coreutils,
  gnutar,
  nix,
  linux-nix,
  dind-image,
}:
{
  scenario,
  variant,
  # The entrypoint (./dind-run.nix) and the result (./result.nix), on Linux.
  entrypoint ? null,
  result ? null,
}:
let
  platform =
    if stdenv.hostPlatform.isLinux then
      ''
        get_entrypoint() { echo ${entrypoint}; }
        store=(-v /nix/store:/nix/store:ro)
        build_result() {
          command nix --extra-experimental-features nix-command build --print-build-logs \
            --out-link "$workdir/result" \
            '${builtins.unsafeDiscardOutputDependency result.drvPath}^out'
        }
      ''
    else
      ''
        get_entrypoint() { ${lib.getExe linux-nix} build scenario-runs.${scenario}.${variant}; }
        store=(-v ${linux-nix.storeVolume}:/nix:ro)
        # The result is in linux-nix's store volume: its logs are copied out.
        build_result() {
          local out
          out="$(${lib.getExe linux-nix} build scenario-results.${scenario}.${variant})"
          if [ -e "$workdir/result" ]; then
            chmod -R u+w "$workdir/result"
            rm -rf "$workdir/result"
          fi
          mkdir -p "$workdir/result"
          ${lib.getExe linux-nix} exec tar -C "$out" -c . | tar -x -C "$workdir/result"
          chmod -R u+w "$workdir/result"
        }
      '';
in
writeShellApplication {
  name = "system-tests-${lib.toLower scenario}-${variant}";
  runtimeInputs = [
    docker-client
    coreutils
    gnutar
    nix
  ];
  text = ''
    ${platform}
    workdir="''${SYSTEM_TESTS_WORKDIR:-$PWD/system-tests-${scenario}-${variant}}"
    mkdir -p "$workdir"
    workdir="$(realpath "$workdir")"

    if [ "$#" = 0 ] && [ -z "''${SYSTEM_TESTS_FORCE:-}" ]; then
      echo "building the ${scenario} result: it runs unless the same inputs passed already" >&2
      build_result
      echo "${scenario} passed, logs in $workdir/result (SYSTEM_TESTS_FORCE=1 runs it again)" >&2
      exit 0
    fi

    entrypoint="$(get_entrypoint)"
    docker image inspect docker:28-dind > /dev/null 2>&1 || docker load < ${dind-image} > /dev/null
    echo "running ${scenario} with its own Docker daemon, logs in $workdir (not cached)" >&2
    exec docker run --rm --privileged --network none --hostname system-tests \
      --name "system-tests-${lib.toLower scenario}-${variant}-$$-$RANDOM" \
      "''${store[@]}" -v "$workdir":/work \
      --entrypoint "$entrypoint" docker:28-dind "$@"
  '';
  passthru = {
    inherit
      scenario
      variant
      entrypoint
      result
      ;
  };
}
