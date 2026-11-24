# The options a scenario module sets: the containers system-tests starts for the scenario, each
# fully declared (image, command, environment, mounts, ports, healthcheck, start order). The result
# is `spec`, the JSON file ./nix_services.py applies to system-tests' containers, and `images`,
# the image tarballs to `docker load` before the run. `sources` says what of the checkout the run
# needs beyond what collecting its tests finds (../sources.nix).
#
# Base modules (./end-to-end.nix) set their values with mkDefault, so a scenario overrides any of
# them with a plain definition, and adds to attribute sets (environment, mounts) by defining more
# keys.
{
  lib,
  config,
  pkgs,
  ...
}:
let
  inherit (lib) mkOption types;

  # A string, null (the variable is unset) or { file = <path>; } (the file's contents, read at run
  # time). Nothing comes from the environment pytest runs in, which is fixed (../dind-run.nix).
  envValue = types.nullOr (
    types.either types.str (
      types.submodule {
        options.file = mkOption { type = types.path; };
      }
    )
  );

  mount = types.submodule {
    options = {
      source = mkOption {
        type = types.str;
        description = ''
          Host path: a store path, or a path under @tests@ (the system-tests directory pytest runs
          in) or @logs@ (the scenario's log folder).
        '';
      };
      readOnly = mkOption {
        type = types.bool;
        default = true;
      };
    };
  };

  service = types.submodule {
    options = {
      image = mkOption {
        type = types.package;
        description = "Image tarball to `docker load`.";
      };
      imageName = mkOption {
        type = types.str;
        description = "The reference `image` is tagged with (name:tag).";
      };
      nixStore = mkOption {
        type = types.bool;
        default = false;
        description = ''
          Mount /nix/store read-only. Images built here carry no store paths: they use the
          mounted ones, so loading them takes no time.
        '';
      };
      # Kept in the form system-tests uses (a string or a list), as both reach the Docker API.
      command = mkOption {
        type = types.nullOr (types.either types.str (types.listOf types.str));
        default = null;
      };
      workingDir = mkOption {
        type = types.nullOr types.str;
        default = null;
      };
      user = mkOption {
        type = types.nullOr types.str;
        default = null;
      };
      environment = mkOption {
        type = types.attrsOf envValue;
        default = { };
      };
      mounts = mkOption {
        type = types.attrsOf mount;
        default = { };
        description = "Bind mounts, by path in the container.";
      };
      # Docker SDK form: "<port>/tcp" = <host port> or [ "<host ip>" <host port> ].
      ports = mkOption {
        type = types.attrsOf (types.either types.int (types.listOf (types.either types.str types.int)));
        default = { };
      };
      # system-tests' form: { test = "<shell command>"; retries = <n>; }, run in the container.
      healthcheck = mkOption {
        type = types.nullOr (types.attrsOf (types.either types.str types.int));
        default = null;
      };
      securityOpt = mkOption {
        type = types.listOf types.str;
        default = [ ];
      };
      capAdd = mkOption {
        type = types.listOf types.str;
        default = [ ];
      };
      privileged = mkOption {
        type = types.bool;
        default = false;
      };
      networkAliases = mkOption {
        type = types.listOf types.str;
        default = [ ];
      };
      dependsOn = mkOption {
        type = types.listOf types.str;
        default = [ ];
        description = "Services that must be healthy before this one starts.";
      };
    };
  };

  toSpec = name: s: {
    image = s.imageName;
    inherit (s)
      command
      user
      healthcheck
      privileged
      ;
    working_dir = s.workingDir;
    environment = lib.mapAttrs (
      _: v: if v == null || builtins.isString v then v else { file = "${v.file}"; }
    ) s.environment;
    mounts = lib.mapAttrs (_: m: {
      inherit (m) source;
      mode = if m.readOnly then "ro" else "rw";
    }) s.mounts;
    inherit (s) ports;
    security_opt = s.securityOpt;
    cap_add = s.capAdd;
    network_aliases = s.networkAliases;
    depends_on = s.dependsOn;
    nix_store = s.nixStore;
    # Unused by the plugin: referencing them keeps what the storeless images use in the closure.
    store_paths = lib.optionals s.nixStore (map toString (s.image.storePaths or [ ]));
  };
  missingDependencies = lib.concatLists (
    lib.mapAttrsToList (
      name: s:
      map (dep: "${name} depends on ${dep}, which is not a service") (
        lib.filter (dep: !config.services ? ${dep}) s.dependsOn
      )
    ) config.services
  );
in
{
  options = {
    scenario = mkOption {
      type = types.str;
      description = "The system-tests scenario (pytest -S).";
    };
    services = mkOption {
      type = types.attrsOf service;
      default = { };
      description = "The scenario's containers, by system-tests' container name (also their hostname).";
    };
    sources = {
      manifests = mkOption {
        type = types.listOf types.str;
        default = [ ];
        description = ''
          The scenario's components (system-tests' scenario.components): only their manifests
          (manifests/<component>.yml) are in its sources (../sources.nix).
        '';
      };
      paths = mkOption {
        type = types.listOf types.str;
        default = [ ];
        description = ''
          Files and directories of the checkout, relative to it, that the run reads and collecting
          the scenario's tests does not (../sources.nix). The mount sources under @tests@ are
          added.
        '';
      };
      allPaths = mkOption {
        type = types.listOf types.str;
        readOnly = true;
        description = "`paths` and the mount sources under @tests@.";
      };
    };
    spec = mkOption {
      type = types.package;
      readOnly = true;
    };
    images = mkOption {
      type = types.listOf types.package;
      readOnly = true;
    };
  };

  config = {
    spec =
      assert lib.assertMsg (missingDependencies == [ ]) (lib.concatStringsSep "\n" missingDependencies);
      pkgs.writeText "system-tests-${lib.toLower config.scenario}-services.json" (
        builtins.toJSON {
          inherit (config) scenario;
          services = lib.mapAttrs toSpec config.services;
        }
      );

    images = lib.unique (lib.mapAttrsToList (_: s: s.image) config.services);

    sources.allPaths = lib.unique (
      config.sources.paths
      ++ lib.concatMap (
        s:
        lib.concatMap (
          m: lib.optional (lib.hasPrefix "@tests@/" m.source) (lib.removePrefix "@tests@/" m.source)
        ) (lib.attrValues s.mounts)
      ) (lib.attrValues config.services)
    );
  };
}
