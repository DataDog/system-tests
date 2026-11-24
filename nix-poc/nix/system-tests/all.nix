# Runs every scenario (`nix run .#system-tests-all`): builds `system-tests-results`, every
# scenario's result (./result.nix) in one build, so Nix runs them in parallel and skips those whose
# inputs passed already. The logs land in <workdir>/result/<SCENARIO>-<variant>.
#
#   Linux:  `nix build` on this machine's store; arguments go to it (e.g. --max-jobs 4)
#   macOS:  `linux-nix build` (./linux-nix.nix), the logs copied out of its store volume;
#           LINUX_NIX_MAX_JOBS bounds how many scenarios run at once
#
# keep-going is on: a failing scenario fails the build once the others are done, and the passing
# ones stay cached. Its logs are then in the build log (-L); its own runner
# (`nix run .#system-tests-<scenario>-<variant>`) gives them as files.
#
# The work directory is ./system-tests-results, or SYSTEM_TESTS_WORKDIR.
{
  lib,
  stdenv,
  writeShellApplication,
  coreutils,
  gnutar,
  nix,
  linux-nix,
}:
{
  # `system-tests-results`, on Linux.
  results ? null,
}:
let
  platform =
    if stdenv.hostPlatform.isLinux then
      ''
        build_results() {
          command nix --extra-experimental-features nix-command build --print-build-logs \
            --keep-going --out-link "$workdir/result" \
            '${builtins.unsafeDiscardOutputDependency results.drvPath}^out' "$@"
        }
      ''
    else
      ''
        build_results() {
          if [ "$#" != 0 ]; then
            echo "system-tests-all takes no arguments on macOS (LINUX_NIX_MAX_JOBS sets max-jobs)" >&2
            exit 2
          fi
          local out
          out="$(${lib.getExe linux-nix} build system-tests-results)"
          if [ -e "$workdir/result" ]; then
            chmod -R u+w "$workdir/result"
            rm -rf "$workdir/result"
          fi
          mkdir -p "$workdir/result"
          # The results are links to each scenario's result: copied dereferenced.
          ${lib.getExe linux-nix} exec tar -C "$out" -ch . | tar -x -C "$workdir/result"
          chmod -R u+w "$workdir/result"
        }
      '';
in
writeShellApplication {
  name = "system-tests-all";
  runtimeInputs = [
    coreutils
    gnutar
    nix
  ];
  text = ''
    ${platform}
    workdir="''${SYSTEM_TESTS_WORKDIR:-$PWD/system-tests-results}"
    mkdir -p "$workdir"
    workdir="$(realpath "$workdir")"

    echo "building every scenario's result: each runs unless the same inputs passed already" >&2
    build_results "$@"
    echo "every scenario passed, logs in $workdir/result/<SCENARIO>-<variant>" >&2
  '';
  passthru = { inherit results; };
}
