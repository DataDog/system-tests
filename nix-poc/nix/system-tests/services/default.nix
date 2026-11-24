# A scenario's services, evaluated from its module (./scenarios/<SCENARIO>.nix) against a weblog:
# `spec` (the JSON ./nix_services.py applies), `images` (to `docker load`), the pytest arguments
# that make system-tests run them (`pytestArgs`, with `pythonPath` on PYTHONPATH), and the
# system-tests sources pytest runs from (`sources`, see ../sources.nix).
{
  lib,
  pkgs,
  runCommand,
  callPackage,
  systemTestsRoot,
  runner,
}:
let
  images = callPackage ../images.nix { inherit runner; };
  mkSources = callPackage ../sources.nix { inherit runner; };

  # The weblog's DD_RC_TUF_ROOT: the TUF root utils/proxy/tuf.py signs with its fixed test key, so
  # it is the same on every run. The module has no system-tests imports.
  tufRoot = runCommand "system-tests-tuf-root" { } ''
    ${runner.env}/bin/python - > "$out" <<'EOF'
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("tuf", "${systemTestsRoot + "/utils/proxy/tuf.py"}")
    tuf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tuf)
    sys.stdout.write(tuf.get_tuf_root_json())
    EOF
  '';

  pythonPath = lib.fileset.toSource {
    root = ./.;
    fileset = ./nix_services.py;
  };
in
{
  scenario,
  # A top-level `weblogs.<variant>`.
  weblog,
}:
let
  inherit
    (lib.evalModules {
      modules = [
        ./module.nix
        (./scenarios + "/${scenario}.nix")
      ];
      specialArgs = {
        inherit
          pkgs
          images
          weblog
          tufRoot
          ;
      };
    })
    config
    ;
in
{
  inherit (config) spec images services;
  inherit pythonPath;
  # Independent of the weblog: the same for every variant.
  sources = mkSources {
    inherit (config) scenario;
    inherit (config.sources) manifests;
    paths = config.sources.allPaths;
  };
  # One argument with "=": pytest takes a separate argument that is not an option for a path, and
  # would make /nix/store its rootdir.
  pytestArgs = [
    "-p"
    "nix_services"
    "--nix-services=${config.spec}"
  ];
}
