# `nix run .#system-tests-vanilla-lock`, from the root of this repository: regenerates
# nix/system-tests-vanilla/lock/*.json for the pinned system-tests (network and a Docker daemon
# needed; nothing of system-tests is modified). Then commit the result.
#
#   SCENARIOS        scenarios to lock (default: those locked already, else DEFAULT)
#   WEBLOGS          python weblog variants (default: fastapi)
#   DDTRACE_VERSION  the ddtrace release to add to the weblog locks and make the default
#                    (default: the latest on PyPI)
#
# The runner lock comes first: the images are listed by system-tests' own code, run with the runner
# it locks (built from this checkout, for this machine).
{
  lib,
  stdenv,
  writeShellApplication,
  python3,
  uv,
  skopeo,
  nix-prefetch-docker,
  docker-client,
  jq,
  nix,
  systemTestsSrc,
}:
let
  python = python3.withPackages (ps: [
    ps.packaging
    ps.pyyaml
  ]);
in
writeShellApplication {
  name = "system-tests-vanilla-lock";
  runtimeInputs = [
    python
    uv
    skopeo
    nix-prefetch-docker
    docker-client
    jq
    nix
  ];
  text = ''
    dir=nix/system-tests-vanilla
    if [ ! -f "$dir/lock.py" ]; then
      echo "run this from the root of the dd-trace-ops checkout" >&2
      exit 1
    fi
    st=${systemTestsSrc}
    lock="$dir/lock"

    python "$dir/lock.py" runner --system-tests "$st" --out "$lock/runner.json"
    runner="$(nix build --no-link --print-out-paths \
      ".#legacyPackages.${stdenv.hostPlatform.system}.system-tests-vanilla.runner")"

    if [ -z "''${SCENARIOS:-}" ] && [ -f "$lock/images.json" ]; then
      SCENARIOS="$(jq -r '.scenarios | keys | join(" ")' "$lock/images.json")"
    fi
    scenario_args=() weblog_args=()
    for s in ''${SCENARIOS:-DEFAULT}; do scenario_args+=(--scenario "$s"); done
    for w in ''${WEBLOGS:-fastapi}; do weblog_args+=(--weblog "python:$w"); done
    python "$dir/lock.py" images --system-tests "$st" --python "$runner/bin/python" \
      "''${scenario_args[@]}" "''${weblog_args[@]}" --out "$lock/images.json"

    for w in ''${WEBLOGS:-fastapi}; do
      python "$dir/lock.py" weblog --system-tests "$st" --variant "$w" \
        ''${DDTRACE_VERSION:+--ddtrace-version "$DDTRACE_VERSION" --default} \
        --out "$lock/weblog-$w.json"
    done
  '';
  meta.description = "Regenerate the locks of nix/system-tests-vanilla";
  passthru = { inherit python; };
}
