# system-tests run as upstream runs it, as a Nix package (see the README's "system-tests, vanilla").
# Instantiated from the shared scope (../default.nix): `systemTestsRoot` is the system-tests input.
#
#   runner                       the test runner's venv (requirements.txt, ./lock/runner.json)
#   images.<reference>           the images system-tests asks for, pinned (./lock/images.json)
#   weblogs.<variant>            the weblog image, built by build.sh (./weblog.nix), an image
#                                derivation of ./image-builder.nix ($out/image.tar, image.json)
#   check                        the locks still match the checkout
#   cores.<SCENARIO>.<variant>   a run against a given Docker daemon (Linux)
#   runs.<SCENARIO>.<variant>    the final, self-contained package: the core in its own
#                                docker:dind (Linux)
#   launchers.<SCENARIO>.<variant>  `nix run` entry points: the package (Linux), or building it
#                                with linux-nix then running it (macOS)
#   lock                         regenerates ./lock (needs network and Docker)
#   imagesInVM.*                 this scope, images built in a VM rather than through Docker
{
  lib,
  stdenv,
  newScope,
  systemTestsRoot,
  flakeSources,
}:
let
  readLock = name: lib.importJSON (./lock + "/${name}.json");
  imagesLock = readLock "images";
  inherit (stdenv.hostPlatform) isLinux;
  forScenarios =
    f:
    lib.mapAttrs (
      scenario: variants: lib.mapAttrs (variant: _: f { inherit scenario variant; }) variants
    ) imagesLock.scenarios;
in
lib.makeScope newScope (self: {
  # How images are built: "docker" or "vm" (./image-builder.nix).
  imageBackend = "docker";
  imageBuilder = self.callPackage ./image-builder.nix { };
  # This scope's attribute path, for linux-nix (./mac.nix).
  scopePath = "system-tests-vanilla";
  imagesInVM = self.overrideScope (
    _: _: {
      imageBackend = "vm";
      scopePath = "system-tests-vanilla.imagesInVM";
    }
  );

  # The pinned system-tests input, as is.
  systemTestsSrc = flakeSources.system-tests or systemTestsRoot;

  runner = self.callPackage ./runner.nix { lock = readLock "runner"; };

  imageSet = self.callPackage ./images.nix { lock = imagesLock; };
  inherit (self.imageSet) images;

  weblogLocks = {
    fastapi = readLock "weblog-fastapi";
  };
  # weblogs.<variant>; `.override { ddtraceVersion = "x.y.z"; }` for another locked release.
  weblogs = lib.mapAttrs (_: lock: self.callPackage ./weblog.nix { inherit lock; }) self.weblogLocks;

  check = self.callPackage ./check.nix { };

  dind-image = self.callPackage ../system-tests/dind-image.nix { };

  cores = lib.optionalAttrs isLinux (forScenarios (self.callPackage ./core.nix { }));
  runs = lib.optionalAttrs isLinux (
    forScenarios (
      args:
      self.callPackage ./package.nix { } (args // { core = self.cores.${args.scenario}.${args.variant}; })
    )
  );
  launchers = if isLinux then self.runs else forScenarios (self.callPackage ./mac.nix { });

  lock = self.callPackage ./lock-app.nix { };
})
