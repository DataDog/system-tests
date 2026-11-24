# The core of a run, independent of where its Docker daemon comes from (./package.nix starts one in a
# docker:dind container; a later launcher may start dockerd in place, in a build):
#
#   system-tests-vanilla-run-<scenario>-<variant> <output dir> [pytest arguments]
#
# with the daemon the docker CLI reaches (DOCKER_HOST, else /var/run/docker.sock) on the same file
# system: system-tests bind-mounts paths of its checkout into its containers.
#
#   1. loads the scenario's images and the weblog into the daemon: nothing is pulled, as
#      system-tests looks for every image locally first (ImageInfo.load);
#   2. copies the pinned system-tests checkout into a fresh directory (it writes there), its logs
#      directory pointing to <output dir>;
#   3. runs `./run.sh +S <SCENARIO> ++ <pytest arguments>`, system-tests' own entry point, with the
#      runner's venv first on PATH and IN_NIX_SHELL set, so it uses that instead of ./venv, from an
#      empty environment (`env -i`) but for the variables below: no host credentials, no
#      USE_IMAGE_MIRROR.
{
  lib,
  writeShellScript,
  runCommand,
  bash,
  coreutils,
  gnused,
  gnugrep,
  findutils,
  docker-client,
  runner,
  systemTestsSrc,
  imageSet,
  weblogs,
  weblogLocks,
  check,
}:
{
  scenario,
  variant,
}:
let
  weblog = weblogs.${variant};
  refs =
    imageSet.scenarios.${scenario}.${variant} or (throw ''
      system-tests-vanilla: ${scenario} on ${variant} is not in the images lock; add it with
        lock.py images --scenario ${scenario} --weblog python:${variant}'');
  # Image tarballs. The base image is only for building the weblog; the weblog is an image
  # derivation (./image-builder.nix), of which only image.tar is used.
  images =
    map (ref: imageSet.images.${ref}) (lib.filter (ref: ref != weblogLocks.${variant}.baseImage) refs)
    ++ [ "${weblog}/image.tar" ];
  logs = if scenario == "DEFAULT" then "logs" else "logs_${lib.toLower scenario}";

  environment = {
    PATH = lib.makeBinPath [
      runner
      docker-client
      bash
      coreutils
      gnused
      gnugrep
      findutils
    ];
    LANG = "C.UTF-8";
    TZ = "UTC";
    PYTHONHASHSEED = "0";
    # run.sh: use the python/pytest on PATH rather than ./venv.
    IN_NIX_SHELL = "pure";
  };
  environmentArgs = lib.escapeShellArgs (lib.mapAttrsToList (n: v: "${n}=${v}") environment);
in
lib.extendDerivation true
  {
    inherit
      scenario
      variant
      images
      weblog
      logs
      ;
  }
  (
    writeShellScript "system-tests-vanilla-run-${lib.toLower scenario}-${variant}" ''
      set -euo pipefail
      export PATH=${environment.PATH}
      # Built only if the locks match the checkout.
      : ${check}
      out="$1"
      shift

      echo "loading ${toString (builtins.length images)} images" >&2
      pids=()
      ${lib.concatMapStrings (image: ''
        docker load -q < ${image} > /dev/null & pids+=($!)
      '') images}
      for pid in "''${pids[@]}"; do wait "$pid"; done

      work="$(mktemp -d)"
      cp -r ${systemTestsSrc} "$work/system-tests"
      chmod -R u+w "$work/system-tests"
      mkdir -p "$work/home" "$out/${logs}"
      rm -rf "$out/${logs}"/* 2>/dev/null || true
      ln -s "$(realpath "$out/${logs}")" "$work/system-tests/${logs}"
      cd "$work/system-tests"

      echo "running ./run.sh +S ${scenario} ++ $*" >&2
      exec env -i ${environmentArgs} HOME="$work/home" \
        ''${DOCKER_HOST:+DOCKER_HOST="$DOCKER_HOST"} \
        ./run.sh +S ${scenario} ++ "$@"
    ''
  )
