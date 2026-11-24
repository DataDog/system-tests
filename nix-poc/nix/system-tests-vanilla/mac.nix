# `nix run` from macOS: two separate steps.
#
#   1. build time: the final package (./package.nix) is built for the Docker VM's Linux with
#      linux-nix (../system-tests/linux-nix.nix), into its store volume (fetches happen here);
#   2. run time: that store path is executed, as is, in a helper container on the same daemon
#      (`--network none`, the store volume and the daemon's socket mounted, the work directory at
#      its own path). Nothing of this script, Nix or linux-nix is used by the run: it is the
#      package's own launcher, with its own closure.
#
# The work directory is ./system-tests-vanilla-<SCENARIO>-<variant>, or $SYSTEM_TESTS_WORKDIR; it
# must be in a directory the Docker VM shares (your home, with colima). Arguments go to pytest.
{
  lib,
  writeShellApplication,
  docker-client,
  coreutils,
  linux-nix,
  scopePath,
}:
{
  scenario,
  variant,
}:
let
  name = "system-tests-vanilla-${lib.toLower scenario}-${variant}";
  image = "nixos/nix:2.34.1";
in
writeShellApplication {
  inherit name;
  runtimeInputs = [
    docker-client
    coreutils
  ];
  text = ''
    package="$(${lib.getExe linux-nix} build ${scopePath}.runs.${scenario}.${variant})"

    workdir="''${SYSTEM_TESTS_WORKDIR:-$PWD/system-tests-vanilla-${scenario}-${variant}}"
    mkdir -p "$workdir"
    workdir="$(realpath "$workdir")"
    docker image inspect ${image} > /dev/null 2>&1 || docker load < ${linux-nix.nixImage} > /dev/null
    exec docker run --rm --network none \
      -v ${linux-nix.storeVolume}:/nix:ro -v /var/run/docker.sock:/var/run/docker.sock \
      -v "$workdir:$workdir" ${image} \
      "$package/bin/${name}" --workdir "$workdir" --store-volume ${linux-nix.storeVolume} -- "$@"
  '';
}
