# The inside of a scenario run (see ./scenario.nix): the entrypoint of a privileged docker:dind
# container, so that each run has its own Docker daemon. system-tests names its containers and
# networks after nothing but the scenario's components and publishes fixed host ports (proxy
# :11111, weblog :7777), so two runs sharing a daemon would collide; with a daemon each, runs only
# share the (read-only) Nix store and can go in parallel.
#
# The script starts the container's daemon, loads the scenario's images (./services) into it,
# copies the scenario's system-tests sources (./sources.nix) into the container and runs pytest
# there, its logs directory pointing to /work (the host directory the logs land in). pytest runs in
# the container too, so the ports system-tests publishes on localhost and the paths it bind-mounts
# are the container's own, /nix/store included. The services run as the scenario module declares
# (./services/nix_services.py). pytest starts from an empty environment but for `environment`
# below, and the outputs of a previous run are removed from /work first: with the container's lack
# of network (./scenario.nix), the run depends on nothing but this script and its arguments.
{
  lib,
  writeShellScript,
  bash,
  coreutils,
  runner,
  mkServices,
}:
{
  scenario,
  # A top-level `weblogs.<variant>`.
  weblog,
}:
let
  services = mkServices { inherit scenario weblog; };
  logs = if scenario == "DEFAULT" then "logs" else "logs_${lib.toLower scenario}";

  # pytest's whole environment.
  environment = {
    # The docker:dind image's, for the docker CLI system-tests falls back to.
    PATH = "/usr/local/bin:/usr/bin:/bin";
    HOME = "/root";
    LANG = "C.UTF-8";
    TZ = "UTC";
    PYTHONHASHSEED = "0";
    PYTHONPATH = "${services.pythonPath}";
  };
  environmentArgs = lib.escapeShellArgs (lib.mapAttrsToList (n: v: "${n}=${v}") environment);
in
# `sources` (and the rest of `services`) evaluate on any platform, the script on Linux only.
lib.extendDerivation true
  {
    inherit services;
    inherit (services) sources;
  }
  (
    writeShellScript "system-tests-run-${lib.toLower scenario}-${weblog.variant}" ''
      set -euo pipefail
      # docker and dockerd-entrypoint.sh come from the docker:dind image (busybox for the rest).

      # /work only receives this run's outputs: nothing a previous run left there is read. It is a
      # host directory (./scenario.nix) or the container's own (./result.nix).
      mkdir -p /work
      rm -rf /work/${logs} /work/dockerd.log

      dockerd-entrypoint.sh dockerd > /work/dockerd.log 2>&1 &
      for _ in $(seq 60); do
        docker info > /dev/null 2>&1 && break
        sleep 1
      done
      docker info > /dev/null

      echo "loading images" >&2
      pids=()
      ${lib.concatMapStrings (image: ''
        docker load < ${image} > /dev/null & pids+=($!)
      '') services.images}
      for pid in "''${pids[@]}"; do wait "$pid"; done

      # The sources go to the container's own file system: the host directory may not allow setting
      # permissions (macOS shares). Only the logs directory points to the host's.
      ${coreutils}/bin/cp -r --no-preserve=mode ${services.sources.src} /system-tests
      mkdir -p /work/${logs}
      ln -s /work/${logs} /system-tests/${logs}
      cd /system-tests
      echo "running ${scenario}" >&2
      # pytest starts from an empty environment: what it, system-tests and the services see is
      # declared here and in the scenario module, and nothing comes from the host. The arguments
      # are what run.sh passes for a single non-parametric scenario, then the script's own.
      exec ${coreutils}/bin/env -i ${environmentArgs} \
        ${runner.env}/bin/python -m pytest -S ${scenario} -p no:warnings -p no:cacheprovider \
        ${lib.escapeShellArgs services.pytestArgs} "$@"
    ''
  )
