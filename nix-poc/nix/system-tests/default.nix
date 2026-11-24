# system-tests weblogs built against this ddtrace, and the scenarios run on them.
#
# Each weblog is built for every interpreter from `minimumPython` on
# (`pythons.<name>.weblogs.<variant>`); the top-level `weblogs.<variant>` uses nixpkgs' default
# `python3`.
{ lib }:
let
  minor = name: lib.toInt (lib.removePrefix "python3" name);
in
rec {
  variants = [ "fastapi" ];

  # Scenarios with a runner, each for every top-level weblog: scenarios.<SCENARIO>.<variant>.
  scenarioNames = [
    "DEFAULT"
    "TRACE_PROPAGATION_STYLE_W3C"
  ];

  # nixpkgs-unstable's python311 package set no longer builds: numpy and sphinx, deep in the
  # weblog closure (test inputs, docs), require 3.12.
  minimumPython = "python312";

  supports = python: lib.versionAtLeast python.pythonVersion "3.${toString (minor minimumPython)}";

  # Per-interpreter attribute set; `callPackage` is the interpreter scope's.
  forPython = callPackage: lib.genAttrs variants (variant: callPackage (./. + "/${variant}.nix") { });

  # What runs inside a scenario's own Docker daemon (Linux only): scenario-runs.<SCENARIO>.<variant>.
  # `callPackage` is the shared scope's; `weblogs` the top-level ones.
  scenarioRuns =
    { callPackage, weblogs }:
    let
      runner = callPackage ./runner.nix { };
      mkRun = callPackage ./dind-run.nix {
        inherit runner;
        mkServices = callPackage ./services { inherit runner; };
      };
    in
    lib.genAttrs scenarioNames (
      scenario: lib.mapAttrs (_: weblog: mkRun { inherit scenario weblog; }) weblogs
    );

  # Scenario runs as derivations (Linux only), their output the run's logs:
  # scenario-results.<SCENARIO>.<variant>. `runs` is `scenarioRuns`' result.
  scenarioResults =
    { callPackage, runs }:
    let
      mkResult = callPackage ./result.nix { dind-image = callPackage ./dind-image.nix { }; };
    in
    lib.mapAttrs (
      scenario: lib.mapAttrs (variant: run: mkResult { inherit run scenario variant; })
    ) runs;

  # `nix run` entry points, on every platform: scenarios.<SCENARIO>.<variant>. `runs` is
  # `scenarioRuns`' result, on Linux.
  scenarios =
    {
      callPackage,
      runs ? null,
      results ? null,
    }:
    let
      mkScenario = callPackage ./scenario.nix { dind-image = callPackage ./dind-image.nix { }; };
    in
    lib.genAttrs scenarioNames (
      scenario:
      lib.genAttrs variants (
        variant:
        mkScenario {
          inherit scenario variant;
          entrypoint = if runs == null then null else runs.${scenario}.${variant};
          result = if results == null then null else results.${scenario}.${variant};
        }
      )
    );
}
