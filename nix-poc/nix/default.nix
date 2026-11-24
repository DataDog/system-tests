# Entry point. Builds ddtrace from the dd-trace-py checkout at `root` as a graph of small
# derivations:
#
#   shared (one per platform):   abseil, libddwaf, dedup-headers, native-headers, python-sources,
#                                dist-info
#   per Python interpreter:      Rust crates (crate2nix) -> _native -> interface stub
#                                dd_wrapper (+ stub) -> _ddup, _stack, _memalloc
#                                IAST _native, plain C extensions, cythonize -> compile per .pyx
#                                wheel -> python-package -> smoke-test
#                                system-tests weblogs (see ./system-tests)
#   system-tests (top level):    the test runner, scenarios.<SCENARIO>.<variant> runners,
#                                scenario-results.<SCENARIO>.<variant> (runs as derivations)
#
# The attributes for the default interpreter are exposed at the top level; other interpreters are
# under `pythons.<name>`.
{
  pkgs,
  crate2nix-cli,
  root,
  # A system-tests checkout, for the weblogs and scenarios.
  systemTestsRoot ? null,
  # name -> store path of the flake and its inputs (self, dd-trace-py, system-tests), used to build
  # Linux weblog images in a container when running scenarios from macOS.
  flakeSources ? { },
  contentAddressed ? true,
  serverless ? false,
}:
let
  inherit (pkgs) lib;

  common = import ./python/common.nix { inherit lib root contentAddressed; };

  systemTests = import ./system-tests { inherit lib; };

  shared = lib.makeScope pkgs.newScope (self: {
    inherit
      crate2nix-cli
      root
      systemTestsRoot
      flakeSources
      common
      serverless
      ;

    libdatadog-src = builtins.fetchGit {
      inherit (common.libdatadog) url rev;
      shallow = true;
    };

    mkCargoNix = self.callPackage ./python/cargo-nix.nix { };

    abseil = self.callPackage ./python/abseil.nix { };
    libddwaf = self.callPackage ./python/libddwaf.nix { };
    dedup-headers = self.callPackage ./python/dedup-headers.nix { };
    native-headers = self.callPackage ./python/native-headers.nix { };
    python-sources = self.callPackage ./python/python-sources.nix { };
    dist-info = self.callPackage ./python/dist-info.nix { };

    # Builds Linux attributes from macOS in a container (system-tests images and scenario tests).
    linux-nix = self.callPackage ./system-tests/linux-nix.nix { };
  });

  forPython =
    python:
    lib.makeScope shared.newScope (
      self:
      {
        inherit python;

        # Interpreter used by build steps that need Cython or setuptools.
        buildPython = python.withPackages (ps: [
          ps.cython
          ps.setuptools
        ]);

        helpers = self.callPackage ./python/helpers.nix { };
        native = self.callPackage ./python/native.nix { };

        profiling = self.callPackage ./python/profiling.nix { };
        iast = self.callPackage ./python/iast.nix { };
        extensions = self.callPackage ./python/extensions.nix { };

        wheel = self.callPackage ./python/wheel.nix { };
        python-package = self.callPackage ./python/python-package.nix { };
        smoke-test = self.callPackage ./python/smoke-test.nix { };
      }
      // lib.optionalAttrs (systemTestsRoot != null && systemTests.supports python) {
        weblogs = systemTests.forPython self.callPackage;
      }
    );

  # The default interpreter's attributes, exposed at the top level.
  default = forPython pkgs.python3;

  # Interpreters supported by both pyproject.toml and the pinned nixpkgs.
  pythons = lib.filterAttrs (_: v: v != null) (
    lib.genAttrs [ "python310" "python311" "python312" "python313" "python314" "python315" ] (
      name:
      let
        attempt = builtins.tryEval (pkgs.${name} or null);
      in
      if attempt.success && attempt.value != null then forPython attempt.value else null
    )
  );
in
{
  inherit (shared)
    abseil
    libddwaf
    dedup-headers
    native-headers
    python-sources
    dist-info
    ;
  inherit pythons;
}
// default
// lib.optionalAttrs (systemTestsRoot != null) {
  system-tests-runner = shared.callPackage ./system-tests/runner.nix { };
  # system-tests run as upstream runs it (see ./system-tests-vanilla).
  system-tests-vanilla = shared.callPackage ./system-tests-vanilla { };
}
// lib.optionalAttrs (!pkgs.stdenv.hostPlatform.isLinux) {
  inherit (shared) linux-nix;
}
// {
  # NixOS test with systemd-nspawn containers (see ./native-testing/test.nix). On Linux, the test
  # itself (the builder needs the `nixos-test` and `uid-range` system features); elsewhere, a
  # script running it in a sandboxed Linux Nix container (see ./native-testing/run.nix).
  native-testing =
    if pkgs.stdenv.hostPlatform.isLinux then
      pkgs.testers.runNixOSTest ./native-testing/test.nix
    else
      shared.callPackage ./native-testing/run.nix { };
}
// lib.optionalAttrs (systemTestsRoot != null) rec {
  scenario-runs = systemTests.scenarioRuns {
    inherit (shared) callPackage;
    inherit (default) weblogs;
  };
  scenario-results = systemTests.scenarioResults {
    inherit (shared) callPackage;
    runs = scenario-runs;
  };
  # Every scenario result, for one `nix build` to run them all in parallel.
  system-tests-results = pkgs.linkFarm "system-tests-results" (
    lib.concatLists (
      lib.mapAttrsToList (
        scenario: variants:
        lib.mapAttrsToList (variant: path: {
          name = "${scenario}-${variant}";
          inherit path;
        }) variants
      ) scenario-results
    )
  );
  # `nix run` entry point running every scenario result (see ./system-tests/all.nix).
  system-tests-all = shared.callPackage ./system-tests/all.nix { } {
    results = if pkgs.stdenv.hostPlatform.isLinux then system-tests-results else null;
  };
  scenarios = systemTests.scenarios {
    inherit (shared) callPackage;
    runs = if pkgs.stdenv.hostPlatform.isLinux then scenario-runs else null;
    results = if pkgs.stdenv.hostPlatform.isLinux then scenario-results else null;
  };
}
