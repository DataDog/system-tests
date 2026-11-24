# A scenario's system-tests sources: the files of the checkout its run reads, so that a system-tests
# change that leaves them alone reproduces them, and with them the scenario's run
# (./dind-run.nix), whose store path stays the same.
#
# Which files those are is found by collecting the scenario's tests (./sources.py): the framework
# collection loads, the test modules holding a selected test and what they import and read, the
# manifests of the scenario's components. The rest of the tests (other scenarios', mostly) and the
# other components' manifests are left out. The index runs on the whole checkout, so it rebuilds on
# every system-tests change, but it is only a list of files; the sources are taken from the checkout
# by that list (import from derivation), so their store path depends on those files alone.
#
# What the run reads that collection does not (the schemas payloads are validated against, the
# files services mount) is declared in the scenario modules (`sources.paths`, ./services).
{
  lib,
  runCommand,
  runner,
  systemTestsRoot,
}:
{
  scenario,
  # The weblogs' library (their system-tests-library label).
  library ? "python",
  # Components whose manifests (manifests/<component>.yml) apply to the scenario.
  manifests,
  # Files and directories of the checkout the run also reads.
  paths,
}:
let
  index =
    runCommand "system-tests-${lib.toLower scenario}-sources.json"
      {
        __structuredAttrs = true;
        inherit
          scenario
          library
          manifests
          paths
          ;
      }
      ''
        export HOME="$TMPDIR"
        ${runner.env}/bin/python ${./sources.py} index ${runner.checkout} "$scenario" "$out" \
          --library="$library" ''${manifests[@]/#/--manifest=} ''${paths[@]/#/--path=}
      '';
  files = builtins.fromJSON (builtins.readFile index);
in
{
  # The sources, in the checkout's layout.
  src = lib.fileset.toSource {
    root = systemTestsRoot;
    fileset = lib.fileset.unions (map (file: systemTestsRoot + "/${file}") files);
  };
  # The list of their files.
  inherit index;
}
