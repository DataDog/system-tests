# Runs the NixOS container test (./test.nix) from macOS: builds
# legacyPackages.<linux system>.native-testing with Nix in a privileged nixos/nix container on the
# Docker daemon the docker CLI points at, sharing linux-nix's image and store volume (see
# ../system-tests/linux-nix.nix).
#
# Unlike linux-nix builds, this one is sandboxed: systemd-nspawn containers need the `uid-range`
# system feature, which needs the sandbox, auto-allocated build UIDs and cgroups. The container is
# privileged for the sandbox's namespaces and mounts and for nspawn.
#
# Arguments go to `nix build`, e.g. `--rebuild` to run the test again. Without arguments, when the
# test already passed, it prints the log of that run instead of building.
{
  lib,
  writeShellApplication,
  docker-client,
  coreutils,
  gnutar,
  linux-nix,
  flakeSources,
}:
let
  inherit (linux-nix) linuxSystem storeVolume nixImage;
in
writeShellApplication {
  name = "native-testing";
  runtimeInputs = [
    docker-client
    coreutils
    gnutar
  ];
  text = ''
    docker image inspect nixos/nix:2.34.1 >/dev/null 2>&1 || docker load < ${nixImage} >&2

    nix_config="$(printf '%s\n' \
      'experimental-features = nix-command flakes ca-derivations auto-allocate-uids cgroups' \
      'sandbox = true' 'auto-allocate-uids = true' 'use-cgroups = true' 'build-users-group =' \
      'system-features = nixos-test uid-range benchmark big-parallel' \
      'build-dir = /nix/var/linux-nix/builds')"

    # The flake and its inputs as this build sees them, so overridden inputs carry over.
    inputs="$(mktemp -d)"
    trap 'rm -rf "$inputs"' EXIT
    ${lib.concatStrings (
      lib.mapAttrsToList (name: path: ''
        ln -s ${path} "$inputs/${name}"
      '') flakeSources
    )}
    echo "running native-testing for ${linuxSystem} in a nixos/nix container" >&2
    tar -C "$inputs" -ch . \
      | docker run -i --rm --privileged -v ${storeVolume}:/nix \
          -e XDG_CACHE_HOME=/nix/var/cache -e NIX_CONFIG="$nix_config" \
          nixos/nix:2.34.1 sh -c '
            set -e
            mkdir -p /nix/var/linux-nix/builds
            inputs="$(mktemp -d /nix/var/linux-nix/inputs.XXXXXX)"
            trap "rm -rf $inputs" EXIT
            tar -x -C "$inputs"
            nargs=$#
            set -- "path:$inputs/self#legacyPackages.${linuxSystem}.native-testing" \
              ${lib.concatMapStrings (name: "--override-input ${name} path:$inputs/${name} ") (
                lib.attrNames (removeAttrs flakeSources [ "self" ])
              )} "$@"
            # A passing result is cached: show the log of the run that produced it.
            if [ "$nargs" = 0 ] && nix path-info "$@" >/dev/null 2>&1; then
              echo "native-testing already passed (pass --rebuild to run it again), its log:" >&2
              nix log "$@"
              nix path-info "$@"
            else
              nix build --print-build-logs --print-out-paths --no-link "$@"
            fi
          ' sh "$@"
  '';
}
